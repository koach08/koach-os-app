"""
GET/POST/PATCH/DELETE /api/ai-services — AI launcher の URL カタログ。
data/ai_services.json に user-editable で持つ。デフォルトはシードで投入。
POST /api/ai-services/{id}/opened で利用回数 + 最終利用時刻を更新 (頻度ソート用)。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import DATA_DIR, now_jst, timestamp_jst

router = APIRouter()

CATALOG_FILE = DATA_DIR / "ai_services.json"

Category = Literal["chat", "code", "research", "writing", "creative", "studio", "other"]


DEFAULT_SERVICES = [
    {"id": "claude", "name": "Claude", "url": "https://claude.ai/new", "emoji": "🧠", "category": "chat", "color": "#d97757", "note": "戦略・長文・思考"},
    {"id": "chatgpt", "name": "ChatGPT", "url": "https://chatgpt.com/", "emoji": "💬", "category": "chat", "color": "#10a37f", "note": "汎用・マルチモーダル"},
    {"id": "venice", "name": "Venice AI", "url": "https://venice.ai/chat", "emoji": "🎭", "category": "chat", "color": "#7c3aed", "note": "uncensored / EGAKU fallback"},
    {"id": "gemini", "name": "Gemini", "url": "https://gemini.google.com/", "emoji": "✨", "category": "chat", "color": "#4285f4", "note": "長文 PDF / 画像"},
    {"id": "grok", "name": "Grok", "url": "https://grok.com/", "emoji": "🌀", "category": "chat", "color": "#1da1f2", "note": "X 連携 / リアルタイム"},
    {"id": "codex", "name": "Codex", "url": "https://chatgpt.com/codex", "emoji": "⌨️", "category": "code", "color": "#000000", "note": "コード生成 / PR"},
    {"id": "claude-code", "name": "Claude Code", "url": "https://docs.claude.com/en/docs/claude-code", "emoji": "🧪", "category": "code", "color": "#d97757", "note": "CLI 経由 (ローカル)"},
    {"id": "perplexity", "name": "Perplexity", "url": "https://perplexity.ai/", "emoji": "🔍", "category": "research", "color": "#20808d", "note": "Web 検索 + 引用"},
    {"id": "notebooklm", "name": "NotebookLM", "url": "https://notebooklm.google.com/", "emoji": "📓", "category": "research", "color": "#1a73e8", "note": "自分のドキュメント RAG"},
    {"id": "genspark", "name": "GenSpark", "url": "https://genspark.ai/", "emoji": "⚡", "category": "research", "color": "#ff5e3a", "note": "自動リサーチ→スライド"},
    {"id": "aistudio", "name": "AI Studio", "url": "https://aistudio.google.com/", "emoji": "🛠", "category": "studio", "color": "#4285f4", "note": "Gemini API テスト"},
    {"id": "grammarly", "name": "Grammarly", "url": "https://app.grammarly.com/", "emoji": "✍️", "category": "writing", "color": "#15c39a", "note": "英文校正"},
    {"id": "canva", "name": "Canva AI", "url": "https://canva.com/", "emoji": "🎨", "category": "creative", "color": "#00c4cc", "note": "スライド・SNS 画像"},
]


class AiService(BaseModel):
    id: str
    name: str
    url: str
    emoji: str = "🤖"
    category: Category = "other"
    color: str = "#71717a"
    note: str = ""
    pinned: bool = False


class ServicePatch(BaseModel):
    name: str | None = None
    url: str | None = None
    emoji: str | None = None
    category: Category | None = None
    color: str | None = None
    note: str | None = None
    pinned: bool | None = None


def _load() -> dict:
    if not CATALOG_FILE.exists():
        data = {
            "services": [{**s, "opened_count": 0, "last_opened": None} for s in DEFAULT_SERVICES],
            "updated_at": timestamp_jst(),
        }
        _write(data)
        return data
    try:
        return json.loads(CATALOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"services": [], "updated_at": None}


def _write(data: dict):
    data["updated_at"] = timestamp_jst()
    CATALOG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/ai-services")
def list_services():
    data = _load()
    return {
        "services": data.get("services", []),
        "updated_at": data.get("updated_at"),
        "now": now_jst().isoformat(),
    }


@router.post("/ai-services")
def add_service(svc: AiService):
    data = _load()
    services = data.get("services", [])
    if any(s.get("id") == svc.id for s in services):
        raise HTTPException(status_code=409, detail=f"id {svc.id} 重複")
    new = {**svc.model_dump(), "opened_count": 0, "last_opened": None}
    services.append(new)
    data["services"] = services
    _write(data)
    return new


@router.patch("/ai-services/{service_id}")
def patch_service(service_id: str, patch: ServicePatch):
    data = _load()
    services = data.get("services", [])
    found = None
    for s in services:
        if s.get("id") == service_id:
            found = s
            break
    if not found:
        raise HTTPException(status_code=404, detail="not found")
    updates = patch.model_dump(exclude_none=True)
    found.update(updates)
    data["services"] = services
    _write(data)
    return found


@router.delete("/ai-services/{service_id}")
def delete_service(service_id: str):
    data = _load()
    data["services"] = [s for s in data.get("services", []) if s.get("id") != service_id]
    _write(data)
    return {"ok": True}


@router.post("/ai-services/{service_id}/opened")
def mark_opened(service_id: str):
    data = _load()
    found = None
    for s in data.get("services", []):
        if s.get("id") == service_id:
            found = s
            break
    if not found:
        raise HTTPException(status_code=404, detail="not found")
    found["opened_count"] = int(found.get("opened_count", 0)) + 1
    found["last_opened"] = timestamp_jst()
    _write(data)
    return found


@router.post("/ai-services/reset")
def reset_to_defaults():
    """シードに戻す (utility)."""
    data = {
        "services": [{**s, "opened_count": 0, "last_opened": None} for s in DEFAULT_SERVICES],
    }
    _write(data)
    return data
