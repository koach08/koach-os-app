"""
音声入力 → 構造化捕捉。
POST /api/voice/transcribe — 音声ファイル (multipart) を Whisper で文字起こし
POST /api/voice/classify   — 文字列を AI が memo / backlog / decision / failure に分類
POST /api/voice/capture    — 上記2つを一発でやって、選んだ宛先に保存
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

from data_manager import (
    DATA_DIR,
    MEMOS_FILE,
    DECISIONS_FILE,
    FAILURES_FILE,
    append_jsonl,
    generate_id,
    get_secret,
    now_jst,
    timestamp_jst,
)
from router import call_ai, DEFAULT_MODELS

router = APIRouter()


def _transcribe_bytes(data: bytes, filename: str = "audio.webm") -> str:
    import openai
    api_key = get_secret("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = openai.OpenAI(api_key=api_key)
    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix or ".webm", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        with open(path, "rb") as audio_file:
            t = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="ja",
            )
        return t.text or ""
    finally:
        try:
            Path(path).unlink()
        except Exception:
            pass


@router.post("/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="audio empty")
    try:
        text = _transcribe_bytes(data, file.filename or "audio.webm")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"whisper failed: {e}")
    return {"text": text}


class ClassifyReq(BaseModel):
    text: str


def _classify(text: str) -> dict:
    system = """あなたは志柿の捕捉アシスタント。短い音声メモ(文字起こし)を以下のいずれかに分類:

- memo: ふと思いついたアイデア、後で見返したいメモ
- backlog: 「〜やる」「〜する必要ある」等のタスク
- decision: 決めたこと、判断
- failure: しくじり、後悔、教訓

JSON で返す:
{"kind": "memo|backlog|decision|failure",
 "title": "(短い要約 30字以内)",
 "body": "(整形した本文)",
 "category": "career|research|creative|family|health|side_project|admin|other",
 "urgency": "high|medium|low"}

ルール: JSON のみ。Markdown 禁止。"""
    raw = call_ai(
        messages=[{"role": "user", "content": text}],
        system=system,
        engine="gpt",
        model=DEFAULT_MODELS.get("gpt", "gpt-4.1-mini"),
        max_tokens=400,
    )
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        import re
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        # 失敗時は memo 扱い
        return {
            "kind": "memo",
            "title": text[:30],
            "body": text,
            "category": "other",
            "urgency": "medium",
        }


@router.post("/voice/classify")
def voice_classify(req: ClassifyReq):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="text empty")
    try:
        return _classify(req.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"classify failed: {e}")


class CaptureReq(BaseModel):
    text: str
    kind: str = ""  # 空なら AI に分類させる
    title: str = ""
    body: str = ""
    category: str = "other"
    urgency: str = "medium"


@router.post("/voice/capture")
def voice_capture(req: CaptureReq):
    text = req.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text empty")
    classified = {
        "kind": req.kind or "",
        "title": req.title or "",
        "body": req.body or text,
        "category": req.category or "other",
        "urgency": req.urgency or "medium",
    }
    if not classified["kind"]:
        try:
            ai = _classify(text)
            classified.update({k: ai.get(k, classified[k]) for k in classified.keys()})
        except Exception:
            classified["kind"] = "memo"

    kind = classified["kind"]
    ts = timestamp_jst()
    if kind == "memo":
        title = classified["title"] or text[:30]
        body = classified["body"] or text
        # memo schema uses `content`; prepend title if distinct
        content = f"{title}\n{body}" if title and title != body[: len(title)] else body
        entry = {
            "id": generate_id("memo"),
            "content": content,
            "color": "yellow",
            "pinned": False,
            "created_at": ts,
            "created_at_ts": int(now_jst().timestamp() * 1000),
            "updated_at": ts,
            "source": "voice",
        }
        append_jsonl(MEMOS_FILE, entry)
    elif kind == "backlog":
        from routers.productivity import _load_backlog, _write_json, BACKLOG_PATH, _next_id
        items = _load_backlog()
        entry = {
            "id": _next_id(),
            "title": classified["title"] or text[:60],
            "category": classified.get("category", "other"),
            "estimated_minutes": 60,
            "urgency": classified.get("urgency", "medium"),
            "notes": classified["body"] if classified["body"] != classified["title"] else "",
            "needs_ai": False,
            "done": False,
            "source": "voice",
            "created_at": ts,
        }
        items.append(entry)
        _write_json(BACKLOG_PATH, items)
    elif kind == "decision":
        entry = {
            "id": generate_id("decision"),
            "title": classified["title"] or text[:60],
            "reasoning": classified["body"],
            "timestamp": ts,
            "source": "voice",
        }
        append_jsonl(DECISIONS_FILE, entry)
    elif kind == "failure":
        entry = {
            "id": generate_id("failure"),
            "what": classified["title"] or text[:60],
            "lesson": classified["body"],
            "timestamp": ts,
            "source": "voice",
        }
        append_jsonl(FAILURES_FILE, entry)
    else:
        raise HTTPException(status_code=400, detail=f"unknown kind: {kind}")

    return {"ok": True, "kind": kind, "saved": entry, "classified": classified}
