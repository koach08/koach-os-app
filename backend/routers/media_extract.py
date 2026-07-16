"""
Gemini multimodal で動画/長尺音声/YouTube URL を構造化抽出。

POST /api/media/extract  multipart upload (video or audio file) → structured
POST /api/media/extract-youtube  { url }                       → structured
POST /api/media/commit          { items, types }                → 既存 endpoint に振り分け投入

抽出される構造:
{
  "summary": "...",
  "decisions":  [{"title":"", "reasoning":""}],
  "tasks":      [{"title":"", "urgency":"", "category":""}],
  "memos":      [{"title":"", "body":""}],
  "events":     [{"title":"", "start_iso":"", "end_iso":"", "location":""}],
  "key_quotes": [{"timestamp":"00:12:34", "text":""}]
}
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from data_manager import (
    DATA_DIR,
    DECISIONS_FILE,
    FAILURES_FILE,
    MEMOS_FILE,
    append_jsonl,
    generate_id,
    get_secret,
    now_jst,
    timestamp_jst,
)

router = APIRouter()


SYSTEM_PROMPT = """You are an extraction assistant analyzing a video, lecture, or recorded conversation.
Output ONLY a single JSON object (no markdown, no commentary) with this exact shape:

{
  "summary": "3-5 文の日本語要約",
  "decisions":  [{"title":"短い決定の見出し", "reasoning":"なぜそう決めたか"}],
  "tasks":      [{"title":"具体的なタスク", "urgency":"high|medium|low", "category":"career|research|creative|family|health|side_project|admin|other"}],
  "memos":      [{"title":"短いタイトル", "body":"後で見返したい示唆・引用・アイデア"}],
  "events":     [{"title":"予定の題", "start_iso":"YYYY-MM-DDTHH:MM:00+09:00 or YYYY-MM-DD", "end_iso":"", "location":""}],
  "key_quotes": [{"timestamp":"HH:MM:SS", "text":"印象的な発言の文字起こし"}]
}

抽出ルール:
- decisions: 「〜することにした」「〜と判断する」など明確に決定された事項のみ
- tasks: 「やる必要がある」「次までに〜」など明確なアクションのみ
- memos: 後で再活用しそうなアイデア・気づき・参考文献・推薦書籍など
- events: 日時が言及された予定 (「次回は来週月曜 14 時」など)。曖昧なら省略
- key_quotes: 5 件まで、印象的・重要な発言を timestamp 付きで
- 該当なしの配列は [] で出す。null は使わない
- 言語は日本語 (元の音声/動画が英語でも要約は日本語)"""


def _gemini_client():
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY not set")
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    return genai


def _upload_and_extract(file_path: Path, mime_type: str) -> dict:
    """Gemini Files API でアップロード → ACTIVE 待ち → generate_content."""
    genai = _gemini_client()
    uploaded = genai.upload_file(path=str(file_path), mime_type=mime_type)
    # PROCESSING → ACTIVE 待ち (動画は数秒〜数十秒)
    waited = 0
    while uploaded.state.name == "PROCESSING":
        if waited > 240:
            raise RuntimeError("Gemini file processing timeout (4 min)")
        time.sleep(3)
        waited += 3
        uploaded = genai.get_file(uploaded.name)
    if uploaded.state.name != "ACTIVE":
        raise RuntimeError(f"Gemini upload failed: state={uploaded.state.name}")
    model = genai.GenerativeModel(
        "gemini-3-flash-preview",
        system_instruction=SYSTEM_PROMPT,
    )
    resp = model.generate_content(
        [uploaded, "上の動画/音声を分析し、指定された JSON 構造で出力してください。"],
        generation_config={"response_mime_type": "application/json", "max_output_tokens": 8192},
    )
    text = (resp.text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        # 強引に最初の { から最後の } までを取る
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise RuntimeError(f"Gemini response not JSON: {text[:200]}")


def _extract_youtube(url: str) -> dict:
    """YouTube URL を Gemini に直接渡す (fileData)."""
    genai = _gemini_client()
    model = genai.GenerativeModel(
        "gemini-3-flash-preview",
        system_instruction=SYSTEM_PROMPT,
    )
    contents = [
        {"file_data": {"mime_type": "video/youtube", "file_uri": url}},
        {"text": "上の YouTube 動画を分析し、指定された JSON 構造で出力してください。"},
    ]
    resp = model.generate_content(
        contents,
        generation_config={"response_mime_type": "application/json", "max_output_tokens": 8192},
    )
    text = (resp.text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise RuntimeError(f"Gemini response not JSON: {text[:200]}")


@router.post("/media/extract")
async def media_extract(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    # Mime 判定
    name = (file.filename or "").lower()
    if file.content_type:
        mime = file.content_type
    elif name.endswith((".mp4", ".mov", ".webm", ".mkv")):
        mime = "video/mp4"
    elif name.endswith((".mp3", ".m4a", ".wav", ".aac", ".ogg")):
        mime = "audio/mp3"
    else:
        mime = "application/octet-stream"

    suffix = Path(name).suffix or (".mp4" if mime.startswith("video") else ".mp3")
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data)
        path = Path(f.name)
    try:
        result = _upload_and_extract(path, mime)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract failed: {e}")
    finally:
        try:
            path.unlink()
        except Exception:
            pass
    result["_meta"] = {"filename": file.filename, "mime": mime, "size_bytes": len(data)}
    return result


class YoutubeReq(BaseModel):
    url: str


@router.post("/media/extract-youtube")
def media_extract_youtube(req: YoutubeReq):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="url empty")
    if not re.match(r"^https?://(www\.)?(youtube\.com|youtu\.be)/", url):
        raise HTTPException(status_code=400, detail="youtube URL required")
    try:
        result = _extract_youtube(url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract failed: {e}")
    result["_meta"] = {"url": url}
    return result


class CommitItem(BaseModel):
    kind: str  # decision / task / memo / event
    data: dict


class CommitReq(BaseModel):
    items: list[CommitItem]


@router.post("/media/commit")
def media_commit(req: CommitReq):
    """抽出済み items を選択して既存ストアに投入。"""
    results: list[dict] = []
    ts = timestamp_jst()
    for item in req.items:
        kind = item.kind
        d = item.data or {}
        try:
            if kind == "decision":
                entry = {
                    "id": generate_id("decision"),
                    "title": (d.get("title", "") or "")[:160],
                    "reasoning": (d.get("reasoning", "") or "")[:1000],
                    "timestamp": ts,
                    "source": "media_extract",
                }
                append_jsonl(DECISIONS_FILE, entry)
                results.append({"ok": True, "kind": "decision", "id": entry["id"]})
            elif kind == "memo":
                title = (d.get("title", "") or "")[:80]
                body = (d.get("body", "") or "")[:2000]
                content = f"{title}\n{body}" if title and title not in body[: len(title)] else body
                entry = {
                    "id": generate_id("memo"),
                    "content": content,
                    "color": "yellow",
                    "pinned": False,
                    "created_at": ts,
                    "created_at_ts": int(now_jst().timestamp() * 1000),
                    "updated_at": ts,
                    "source": "media_extract",
                }
                append_jsonl(MEMOS_FILE, entry)
                results.append({"ok": True, "kind": "memo", "id": entry["id"]})
            elif kind == "task":
                from routers.productivity import _load_backlog, _write_json, BACKLOG_PATH, _next_id
                items = _load_backlog()
                entry = {
                    "id": _next_id(),
                    "title": (d.get("title", "") or "")[:160],
                    "category": d.get("category", "other"),
                    "estimated_minutes": 60,
                    "urgency": d.get("urgency", "medium"),
                    "notes": "",
                    "needs_ai": False,
                    "done": False,
                    "source": "media_extract",
                    "created_at": ts,
                }
                items.append(entry)
                _write_json(BACKLOG_PATH, items)
                results.append({"ok": True, "kind": "task", "id": entry["id"]})
            elif kind == "event":
                from gcal import is_configured, create_event
                if not is_configured():
                    results.append({"ok": False, "kind": "event", "error": "calendar not configured"})
                    continue
                start = d.get("start_iso", "")
                end = d.get("end_iso", "") or start
                if not start:
                    results.append({"ok": False, "kind": "event", "error": "start required"})
                    continue
                ev = create_event(
                    title=(d.get("title", "") or "(無題)"),
                    start_iso=start,
                    end_iso=end,
                    description="[media_extract]",
                    location=d.get("location", ""),
                )
                results.append({"ok": True, "kind": "event", "id": ev.get("id", ""), "html_link": ev.get("htmlLink", "")})
            else:
                results.append({"ok": False, "kind": kind, "error": "unknown kind"})
        except Exception as e:
            results.append({"ok": False, "kind": kind, "error": str(e)})
    return {"count": len(results), "results": results}
