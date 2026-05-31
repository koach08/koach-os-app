"""
Koach Agent — Claude tool calling loop.

POST /api/agent/upload  multipart → returns file_id (temp 保存 30 分)
POST /api/agent/chat   { message, history, attachments? } → エージェント結果

ツール:
- web_search        : DuckDuckGo
- web_fetch         : URL → text
- analyze_image     : Claude vision で画像分析
- analyze_pdf       : Gemini multimodal で PDF 分析
- analyze_video_url : Gemini で YouTube 解析
- analyze_audio     : Whisper 文字起こし
- search_my_data    : memo / decision / failure / private RAG 検索
- list_calendar     : 今日〜N日の予定
- create_event      : Google Calendar に書き込み
- add_backlog       : Coach バックログ追加
- save_memo         : メモ保存
- save_decision     : 決定記録
- tts_speak         : Gemini TTS で音声化 (mp3 file_id 返す)
"""

from __future__ import annotations

import base64
import json
import re
import tempfile
import time
import uuid
from pathlib import Path
from datetime import timedelta
from typing import Any

import requests
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from data_manager import (
    DATA_DIR,
    DECISIONS_FILE,
    MEMOS_FILE,
    append_jsonl,
    generate_id,
    get_secret,
    now_jst,
    timestamp_jst,
)
from router import DEFAULT_MODELS

router = APIRouter()

UPLOAD_DIR = DATA_DIR / "agent_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_TTL_SEC = 3600 * 2  # 2 時間で掃除


def _cleanup_old_uploads():
    now_ts = time.time()
    for p in UPLOAD_DIR.iterdir():
        try:
            if now_ts - p.stat().st_mtime > UPLOAD_TTL_SEC:
                p.unlink()
        except Exception:
            pass


def _resolve_upload(file_id: str) -> Path:
    p = UPLOAD_DIR / file_id
    if not p.exists():
        raise ValueError(f"file_id {file_id} not found")
    return p


# ─── File upload ────────────────────────────────────────────

@router.post("/agent/upload")
async def agent_upload(file: UploadFile = File(...)):
    _cleanup_old_uploads()
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    fid = uuid.uuid4().hex + "_" + (file.filename or "upload").replace("/", "_")[-80:]
    path = UPLOAD_DIR / fid
    path.write_bytes(data)
    mime = file.content_type or "application/octet-stream"
    return {
        "file_id": fid,
        "filename": file.filename,
        "mime": mime,
        "size_bytes": len(data),
    }


# ─── Tool implementations ───────────────────────────────────

def tool_web_search(query: str, max_results: int = 6) -> str:
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return "(web_search disabled: ddgs/duckduckgo_search not installed)"
    out = []
    try:
        with DDGS() as ddgs:
            for r in list(ddgs.text(query, max_results=max_results)):
                out.append(f"- {r.get('title','')}\n  {r.get('href','')}\n  {r.get('body','')[:200]}")
    except Exception as e:
        return f"(search error: {e})"
    return "\n\n".join(out) or "(該当結果なし)"


def tool_web_fetch(url: str, max_chars: int = 8000) -> str:
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 Koach-OS-Agent"})
        r.raise_for_status()
    except Exception as e:
        return f"(fetch error: {e})"
    text = r.text
    # 雑に HTML タグ除去
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars] + (f"\n\n... ({len(text)} chars total)" if len(text) > max_chars else "")


def tool_analyze_image(prompt: str, file_id: str | None = None, url: str | None = None) -> str:
    """Claude vision で画像分析。"""
    import anthropic
    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        return "(ANTHROPIC_API_KEY not set)"
    if file_id:
        p = _resolve_upload(file_id)
        data = p.read_bytes()
        mime = "image/jpeg"
        n = p.name.lower()
        if n.endswith(".png"): mime = "image/png"
        elif n.endswith(".webp"): mime = "image/webp"
        elif n.endswith(".gif"): mime = "image/gif"
        source = {"type": "base64", "media_type": mime, "data": base64.b64encode(data).decode()}
    elif url:
        source = {"type": "url", "url": url}
    else:
        return "(file_id or url required)"
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=DEFAULT_MODELS.get("claude", "claude-opus-4-8"),
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": source},
                {"type": "text", "text": prompt or "この画像を詳しく説明してください"},
            ],
        }],
    )
    return resp.content[0].text


def tool_analyze_pdf(prompt: str, file_id: str | None = None) -> str:
    """Gemini multimodal で PDF 分析。"""
    if not file_id:
        return "(PDF file_id 必須)"
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return "(GEMINI_API_KEY not set)"
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    p = _resolve_upload(file_id)
    uploaded = genai.upload_file(path=str(p), mime_type="application/pdf")
    waited = 0
    while uploaded.state.name == "PROCESSING":
        if waited > 60:
            return "(PDF processing timeout)"
        time.sleep(2)
        waited += 2
        uploaded = genai.get_file(uploaded.name)
    if uploaded.state.name != "ACTIVE":
        return f"(upload failed: {uploaded.state.name})"
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    resp = model.generate_content([uploaded, prompt or "この PDF の要点を 5 点で"], generation_config={"max_output_tokens": 4000})
    return resp.text or ""


def tool_analyze_video_url(url: str, prompt: str) -> str:
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return "(GEMINI_API_KEY not set)"
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-2.0-flash-exp")
    contents = [
        {"file_data": {"mime_type": "video/youtube", "file_uri": url}},
        {"text": prompt or "この動画の要点を 5 点で"},
    ]
    try:
        resp = model.generate_content(contents, generation_config={"max_output_tokens": 4000})
        return resp.text or ""
    except Exception as e:
        return f"(video analysis error: {e})"


def tool_analyze_audio(file_id: str, prompt: str = "") -> str:
    """Whisper transcribe → 要点。"""
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        return "(OPENAI_API_KEY not set)"
    import openai
    client = openai.OpenAI(api_key=api_key)
    p = _resolve_upload(file_id)
    with open(p, "rb") as f:
        t = client.audio.transcriptions.create(model="whisper-1", file=f, language="ja")
    text = t.text or ""
    if not prompt:
        return text
    # 要点抽出を AI に
    from router import call_ai
    summary = call_ai(
        messages=[{"role": "user", "content": f"以下の音声文字起こしについて:\n\n{text}\n\n質問: {prompt}"}],
        system="文字起こしを元に質問に簡潔に答える。",
        engine="claude",
        model=DEFAULT_MODELS["claude"],
        max_tokens=1500,
    )
    return f"## 文字起こし\n{text[:2000]}\n\n## 回答\n{summary}"


def tool_search_my_data(query: str) -> str:
    try:
        from routers.rag_query import rag_query, RagQuery
        result = rag_query(RagQuery(query=query, top_k=6, engine="claude"))
        cites = "\n".join(
            f"[{c['index']}] ({c['kind']}, {c['timestamp'][:10]}) {c['title']}: {c['excerpt'][:200]}"
            for c in result.get("citations", [])
        )
        return f"## 回答\n{result.get('answer','')}\n\n## 引用元\n{cites}"
    except Exception as e:
        return f"(RAG error: {e}. /api/rag/reindex が必要かも)"


def tool_list_calendar(days_ahead: int = 1) -> str:
    try:
        from gcal import is_configured, list_upcoming_events
        if not is_configured():
            return "(Google Calendar 未連携)"
        evs = list_upcoming_events(days_ahead=days_ahead)
        if not evs:
            return "(予定なし)"
        return "\n".join(
            f"- {e['start_iso'][:16]} {e['title']}" + (f" @ {e['location']}" if e.get("location") else "")
            for e in evs[:30]
        )
    except Exception as e:
        return f"(error: {e})"


def tool_create_event(title: str, start_iso: str, end_iso: str, description: str = "", location: str = "") -> str:
    try:
        from gcal import is_configured, create_event
        if not is_configured():
            return "(Google Calendar 未連携)"
        ev = create_event(title=title, start_iso=start_iso, end_iso=end_iso, description=description, location=location)
        return f"✓ 作成: {ev.get('id','')} {ev.get('htmlLink','')}"
    except Exception as e:
        return f"(error: {e})"


def tool_add_backlog(title: str, category: str = "other", urgency: str = "medium", estimated_minutes: int = 60, notes: str = "") -> str:
    try:
        from routers.productivity import _load_backlog, _write_json, BACKLOG_PATH, _next_id
        items = _load_backlog()
        entry = {
            "id": _next_id(),
            "title": title,
            "category": category,
            "urgency": urgency,
            "estimated_minutes": estimated_minutes,
            "notes": notes,
            "needs_ai": False,
            "done": False,
            "source": "agent",
            "created_at": timestamp_jst(),
        }
        items.append(entry)
        _write_json(BACKLOG_PATH, items)
        return f"✓ backlog 追加: {entry['id']} {title}"
    except Exception as e:
        return f"(error: {e})"


def tool_save_memo(content: str) -> str:
    try:
        ts = timestamp_jst()
        entry = {
            "id": generate_id("memo"),
            "content": content,
            "color": "yellow",
            "pinned": False,
            "created_at": ts,
            "created_at_ts": int(now_jst().timestamp() * 1000),
            "updated_at": ts,
            "source": "agent",
        }
        append_jsonl(MEMOS_FILE, entry)
        return f"✓ memo 保存: {entry['id']}"
    except Exception as e:
        return f"(error: {e})"


def tool_save_decision(title: str, reasoning: str) -> str:
    try:
        entry = {
            "id": generate_id("decision"),
            "title": title,
            "reasoning": reasoning,
            "timestamp": timestamp_jst(),
            "source": "agent",
        }
        append_jsonl(DECISIONS_FILE, entry)
        return f"✓ decision 保存: {entry['id']}"
    except Exception as e:
        return f"(error: {e})"


def tool_tts_speak(text: str, voice: str = "Kore") -> str:
    """Gemini TTS で音声化、file_id 返す (frontend で再生)."""
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return "(GEMINI_API_KEY not set)"
    try:
        # Gemini TTS API は preview。ここでは google-genai SDK 想定だが
        # 古い google-generativeai では未サポート。フォールバックとして OpenAI TTS を使う
        openai_key = get_secret("OPENAI_API_KEY")
        if openai_key:
            import openai
            client = openai.OpenAI(api_key=openai_key)
            resp = client.audio.speech.create(model="tts-1", voice="nova", input=text[:4000])
            fid = uuid.uuid4().hex + "_tts.mp3"
            path = UPLOAD_DIR / fid
            path.write_bytes(resp.content)
            return f"✓ 音声生成: file_id={fid} (mp3, /api/agent/file/{fid} で再生可)"
        return "(TTS unavailable: OPENAI_API_KEY needed for fallback)"
    except Exception as e:
        return f"(TTS error: {e})"


# ─── Anthropic tool schema ────────────────────────────────

TOOL_SCHEMA: list[dict] = [
    {
        "name": "web_search",
        "description": "DuckDuckGo で Web 検索。最新情報・事実確認に。",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "web_fetch",
        "description": "URL を取得して本文を返す (HTML タグ除去済)。",
        "input_schema": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    },
    {
        "name": "analyze_image",
        "description": "画像を Claude vision で分析。file_id (アップロード済) または URL のいずれか。OCR・図解読解・状況描写に。",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "聞きたいこと"},
                "file_id": {"type": "string"},
                "url": {"type": "string"},
            },
            "required": ["prompt"],
        },
    },
    {
        "name": "analyze_pdf",
        "description": "PDF を Gemini で読み、質問に答える。file_id 必須 (事前に upload)。",
        "input_schema": {
            "type": "object",
            "properties": {
                "prompt": {"type": "string"},
                "file_id": {"type": "string"},
            },
            "required": ["prompt", "file_id"],
        },
    },
    {
        "name": "analyze_video_url",
        "description": "YouTube URL を Gemini multimodal で分析。文字起こし・要点抽出・引用タイムスタンプ可。",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}, "prompt": {"type": "string"}},
            "required": ["url", "prompt"],
        },
    },
    {
        "name": "analyze_audio",
        "description": "音声ファイル (file_id) を Whisper で文字起こし + 必要なら質問に回答。",
        "input_schema": {
            "type": "object",
            "properties": {"file_id": {"type": "string"}, "prompt": {"type": "string"}},
            "required": ["file_id"],
        },
    },
    {
        "name": "search_my_data",
        "description": "志柿の memo / decision / failure / private chat / backlog を意味検索 + 引用付き回答。「過去の自分はどう決めたか」を聞く時に。",
        "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    {
        "name": "list_calendar",
        "description": "Google Calendar の今日〜N日の予定一覧。",
        "input_schema": {"type": "object", "properties": {"days_ahead": {"type": "integer", "default": 1}}},
    },
    {
        "name": "create_event",
        "description": "Google Calendar に予定を作成。ISO 8601 +09:00 形式。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start_iso": {"type": "string"},
                "end_iso": {"type": "string"},
                "description": {"type": "string"},
                "location": {"type": "string"},
            },
            "required": ["title", "start_iso", "end_iso"],
        },
    },
    {
        "name": "add_backlog",
        "description": "Coach バックログにタスクを追加。",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "category": {"type": "string", "enum": ["career", "research", "creative", "family", "health", "learning", "side_project", "admin", "rest", "other"]},
                "urgency": {"type": "string", "enum": ["high", "medium", "low"]},
                "estimated_minutes": {"type": "integer"},
                "notes": {"type": "string"},
            },
            "required": ["title"],
        },
    },
    {
        "name": "save_memo",
        "description": "memo に保存 (sticky note)。",
        "input_schema": {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]},
    },
    {
        "name": "save_decision",
        "description": "決定ログに記録 (title + reasoning)。",
        "input_schema": {"type": "object", "properties": {"title": {"type": "string"}, "reasoning": {"type": "string"}}, "required": ["title", "reasoning"]},
    },
    {
        "name": "tts_speak",
        "description": "テキストを音声化 (mp3) して file_id 返す。Daily Brief を聞くなど。",
        "input_schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
    },
]


TOOL_FUNCS = {
    "web_search": lambda i: tool_web_search(i["query"]),
    "web_fetch": lambda i: tool_web_fetch(i["url"]),
    "analyze_image": lambda i: tool_analyze_image(i.get("prompt", ""), i.get("file_id"), i.get("url")),
    "analyze_pdf": lambda i: tool_analyze_pdf(i.get("prompt", ""), i.get("file_id")),
    "analyze_video_url": lambda i: tool_analyze_video_url(i["url"], i.get("prompt", "")),
    "analyze_audio": lambda i: tool_analyze_audio(i["file_id"], i.get("prompt", "")),
    "search_my_data": lambda i: tool_search_my_data(i["query"]),
    "list_calendar": lambda i: tool_list_calendar(i.get("days_ahead", 1)),
    "create_event": lambda i: tool_create_event(i["title"], i["start_iso"], i["end_iso"], i.get("description", ""), i.get("location", "")),
    "add_backlog": lambda i: tool_add_backlog(i["title"], i.get("category", "other"), i.get("urgency", "medium"), i.get("estimated_minutes", 60), i.get("notes", "")),
    "save_memo": lambda i: tool_save_memo(i["content"]),
    "save_decision": lambda i: tool_save_decision(i["title"], i["reasoning"]),
    "tts_speak": lambda i: tool_tts_speak(i["text"]),
}


SYSTEM_PROMPT = """あなたは Koach OS の中で動くエージェント。志柿浩一郎 (大学教員 + 個人開発複数並走、家族あり) を補佐する。

利用できる道具:
- web_search / web_fetch: Web から最新情報
- analyze_image / analyze_pdf / analyze_video_url / analyze_audio: マルチモーダル分析
- search_my_data: 志柿の過去 memo / decision / failure / private chat を引用付き検索
- list_calendar / create_event: Google Calendar 操作
- add_backlog / save_memo / save_decision: Koach OS のストアに書き込み
- tts_speak: テキスト音声化

行動指針:
- まず何をすべきか考えてから道具を使う。道具の濫用は避ける (3-5 ステップに収まる前提で計画)
- 過去の決定や好みに照らす必要がある時は search_my_data を先に
- Calendar / バックログ書き込み前に「ユーザーに確認するか、即時実行するか」判断
  - 明示的に「入れて」「追加して」とあれば即時、それ以外は提案だけして確認待ち
- 出力スタイル: です/ます調、簡潔、抽象名詞「〜性」「重要性」NG、em ダッシュ NG、一人称「自分」(僕 NG)
- 数字や事実は道具で確認してから書く。憶測を断言しない
- 最後に必ず「次の一手」を 1 つだけ示す (やらない選択も含む)
"""


class AgentChatReq(BaseModel):
    message: str
    history: list[dict] = []  # [{"role":"user|assistant","content":"..."}]
    attachments: list[dict] = []  # [{"file_id":"...", "filename":"...", "mime":"..."}]
    max_steps: int = 6
    engine_model: str = ""  # override


@router.post("/agent/chat")
def agent_chat(req: AgentChatReq):
    import anthropic
    api_key = get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(500, "ANTHROPIC_API_KEY not set")
    client = anthropic.Anthropic(api_key=api_key)
    model = req.engine_model or DEFAULT_MODELS.get("claude", "claude-opus-4-8")

    # 添付ファイル情報を user メッセージに付ける (file_id 表で渡す)
    attach_note = ""
    if req.attachments:
        attach_note = "\n\n## 添付ファイル\n" + "\n".join(
            f"- file_id={a['file_id']}  filename={a.get('filename','')}  mime={a.get('mime','')}"
            for a in req.attachments
        )

    messages: list[dict] = []
    for h in req.history[-20:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": req.message + attach_note})

    steps: list[dict] = []
    final_text = ""

    for step_i in range(req.max_steps):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=4000,
                system=SYSTEM_PROMPT,
                tools=TOOL_SCHEMA,
                messages=messages,
            )
        except Exception as e:
            raise HTTPException(500, f"Claude error: {e}")

        # text + tool_use ブロックを記録
        text_parts: list[str] = []
        tool_uses: list[dict] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_uses.append({"id": block.id, "name": block.name, "input": block.input})

        text_now = "".join(text_parts).strip()
        if text_now:
            steps.append({"type": "thought", "content": text_now})

        if resp.stop_reason == "tool_use" and tool_uses:
            messages.append({"role": "assistant", "content": resp.content})  # original blocks
            tool_results = []
            for tu in tool_uses:
                fn = TOOL_FUNCS.get(tu["name"])
                if not fn:
                    result = f"(unknown tool: {tu['name']})"
                else:
                    try:
                        result = fn(tu["input"])
                    except Exception as e:
                        result = f"(tool {tu['name']} error: {e})"
                result_str = str(result)[:8000]
                steps.append({
                    "type": "tool",
                    "tool_name": tu["name"],
                    "tool_input": tu["input"],
                    "tool_result": result_str,
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu["id"],
                    "content": result_str,
                })
            messages.append({"role": "user", "content": tool_results})
            continue

        # 終了
        final_text = text_now
        break
    else:
        final_text = "(max_steps に到達)"

    return {
        "final": final_text,
        "steps": steps,
        "step_count": len(steps),
        "generated_at": now_jst().isoformat(),
        "model_used": model,
    }


# ─── File serving (TTS 等の結果再生用) ──────────────────

from fastapi.responses import FileResponse


@router.get("/agent/file/{file_id}")
def get_agent_file(file_id: str):
    p = UPLOAD_DIR / file_id
    if not p.exists():
        raise HTTPException(404, "not found")
    return FileResponse(p)
