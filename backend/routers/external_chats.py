"""
外部 AI チャット履歴 import + 一覧 + 続き相談

Phase 1:
- POST /external-chats/import-chatgpt  : ChatGPT export (conversations.json) を取り込み
- POST /external-chats/import-claude   : Claude.ai export (conversations.json) を取り込み
- GET  /external-chats                  : 一覧 (title, provider, date, message count)
- GET  /external-chats/{id}             : 単一 conversation 全文取得
- POST /external-chats/{id}/continue    : 続き相談 (履歴を context に新しい返答を生成)
- DELETE /external-chats/{id}           : 削除

データ:
- data/external_chats.jsonl  各 conversation 1 行 JSON
  schema: { id, provider, title, created_at, updated_at, messages: [{role, content, ts}], imported_at }
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import DATA_DIR, now_jst, timestamp_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

EXT_CHATS_FILE = DATA_DIR / "external_chats.jsonl"


# ---------- 内部 helpers ----------

def _load_all() -> list[dict]:
    if not EXT_CHATS_FILE.exists():
        return []
    out: list[dict] = []
    for line in EXT_CHATS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def _write_all(items: list[dict]) -> None:
    EXT_CHATS_FILE.write_text(
        "\n".join(json.dumps(it, ensure_ascii=False) for it in items) + ("\n" if items else ""),
        encoding="utf-8",
    )


def _ts_iso(value) -> str:
    """epoch float / ISO string / None → ISO string"""
    if value is None or value == "":
        return ""
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value).isoformat()
        except Exception:
            return ""
    return str(value)


# ---------- ChatGPT export parser ----------

def _parse_chatgpt_conversations(raw: list[dict]) -> list[dict]:
    """ChatGPT conversations.json の各 conversation を統一形式に変換"""
    out: list[dict] = []
    for conv in raw:
        try:
            mapping = conv.get("mapping") or {}
            # message 順に並べる: create_time 昇順
            msgs = []
            for node_id, node in mapping.items():
                m = node.get("message") if isinstance(node, dict) else None
                if not m:
                    continue
                author = (m.get("author") or {}).get("role")
                if author not in ("user", "assistant", "system"):
                    continue
                content = m.get("content") or {}
                parts = content.get("parts") or []
                text_parts = []
                for p in parts:
                    if isinstance(p, str):
                        text_parts.append(p)
                    elif isinstance(p, dict):
                        text_parts.append(p.get("text", "") or "")
                text = "\n".join(t for t in text_parts if t).strip()
                if not text:
                    continue
                msgs.append({
                    "role": author,
                    "content": text,
                    "ts": _ts_iso(m.get("create_time")),
                })
            msgs.sort(key=lambda x: x.get("ts", ""))
            if not msgs:
                continue
            out.append({
                "id": f"chatgpt-{conv.get('id') or uuid.uuid4().hex[:8]}",
                "provider": "chatgpt",
                "title": conv.get("title") or "(no title)",
                "created_at": _ts_iso(conv.get("create_time")),
                "updated_at": _ts_iso(conv.get("update_time")),
                "messages": msgs,
                "imported_at": timestamp_jst(),
            })
        except Exception:
            continue
    return out


# ---------- Claude.ai export parser ----------

def _parse_claude_conversations(raw: list[dict]) -> list[dict]:
    """Claude.ai conversations.json の各 conversation を統一形式に変換"""
    out: list[dict] = []
    for conv in raw:
        try:
            chat_messages = conv.get("chat_messages") or []
            msgs = []
            for cm in chat_messages:
                sender = cm.get("sender", "")
                role = "assistant" if sender == "assistant" else "user"
                text = cm.get("text") or ""
                # 新フォーマットの content (list of blocks) にも対応
                if not text and isinstance(cm.get("content"), list):
                    parts = []
                    for block in cm["content"]:
                        if isinstance(block, dict) and block.get("type") == "text":
                            parts.append(block.get("text", ""))
                    text = "\n".join(parts).strip()
                if not text:
                    continue
                msgs.append({
                    "role": role,
                    "content": text,
                    "ts": _ts_iso(cm.get("created_at")),
                })
            msgs.sort(key=lambda x: x.get("ts", ""))
            if not msgs:
                continue
            out.append({
                "id": f"claude-{conv.get('uuid') or uuid.uuid4().hex[:8]}",
                "provider": "claude",
                "title": conv.get("name") or "(no title)",
                "created_at": _ts_iso(conv.get("created_at")),
                "updated_at": _ts_iso(conv.get("updated_at")),
                "messages": msgs,
                "imported_at": timestamp_jst(),
            })
        except Exception:
            continue
    return out


# ---------- import endpoints ----------

class ImportReq(BaseModel):
    raw_json: str  # conversations.json の中身を文字列で受ける (frontend が読んで投げる想定)


def _merge(new_convs: list[dict]) -> dict:
    existing = _load_all()
    by_id = {it["id"]: it for it in existing}
    added = 0
    updated = 0
    for c in new_convs:
        if c["id"] in by_id:
            # 更新 (message が増えていれば差し替え)
            old = by_id[c["id"]]
            if len(c["messages"]) > len(old.get("messages", [])):
                by_id[c["id"]] = c
                updated += 1
        else:
            by_id[c["id"]] = c
            added += 1
    merged = sorted(by_id.values(), key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
    _write_all(merged)
    return {"ok": True, "added": added, "updated": updated, "total": len(merged)}


@router.post("/external-chats/import-chatgpt")
def import_chatgpt(req: ImportReq):
    try:
        raw = json.loads(req.raw_json)
    except Exception as e:
        raise HTTPException(400, f"invalid JSON: {e}")
    if not isinstance(raw, list):
        raise HTTPException(400, "conversations.json の root は配列であるべき")
    parsed = _parse_chatgpt_conversations(raw)
    return _merge(parsed)


@router.post("/external-chats/import-claude")
def import_claude(req: ImportReq):
    try:
        raw = json.loads(req.raw_json)
    except Exception as e:
        raise HTTPException(400, f"invalid JSON: {e}")
    if not isinstance(raw, list):
        raise HTTPException(400, "conversations.json の root は配列であるべき")
    parsed = _parse_claude_conversations(raw)
    return _merge(parsed)


# ---------- list / detail / continue / delete ----------

@router.get("/external-chats")
def list_chats(provider: str | None = None, limit: int = 200):
    items = _load_all()
    if provider:
        items = [it for it in items if it.get("provider") == provider]
    items.sort(key=lambda x: x.get("updated_at") or x.get("created_at") or "", reverse=True)
    summary = [
        {
            "id": it["id"],
            "provider": it["provider"],
            "title": it["title"],
            "created_at": it.get("created_at", ""),
            "updated_at": it.get("updated_at", ""),
            "message_count": len(it.get("messages", [])),
            "preview": (it["messages"][0]["content"][:120] if it.get("messages") else ""),
        }
        for it in items[:limit]
    ]
    return {"items": summary, "count": len(summary), "total": len(items)}


@router.get("/external-chats/{chat_id}")
def get_chat(chat_id: str):
    for it in _load_all():
        if it["id"] == chat_id:
            return it
    raise HTTPException(404, "not found")


class ContinueReq(BaseModel):
    user_message: str
    engine: str = "claude"
    include_messages: int = 20  # 直近 N メッセージを context に


@router.post("/external-chats/{chat_id}/continue")
def continue_chat(chat_id: str, body: ContinueReq):
    chat = None
    items = _load_all()
    for it in items:
        if it["id"] == chat_id:
            chat = it
            break
    if not chat:
        raise HTTPException(404, "not found")

    # 直近 N message を context に
    history = (chat.get("messages") or [])[-max(2, body.include_messages):]

    # system: 過去の会話を引き継いで返答
    system = (
        f"あなたは過去に {chat['provider']} 上で行われた以下の対話の続きを返答する。"
        f" 会話のテーマ: 「{chat.get('title', '')}」。"
        f" 過去の流れを尊重しつつ、ユーザーの新しい質問に答える。"
    )

    messages = []
    for m in history:
        role = m.get("role")
        if role not in ("user", "assistant"):
            continue
        messages.append({"role": role, "content": m.get("content", "")})
    messages.append({"role": "user", "content": body.user_message})

    engine = body.engine if body.engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS[engine]
    try:
        reply = call_ai(messages=messages, system=system, engine=engine, model=model, max_tokens=2000)
    except Exception as e:
        raise HTTPException(500, f"AI call failed: {e}")

    # 続きの message を保存
    chat.setdefault("messages", []).append({
        "role": "user",
        "content": body.user_message,
        "ts": timestamp_jst(),
    })
    chat["messages"].append({
        "role": "assistant",
        "content": reply,
        "ts": timestamp_jst(),
        "_engine": engine,
        "_model": model,
    })
    chat["updated_at"] = timestamp_jst()
    _write_all(items)

    return {"ok": True, "reply": reply, "engine": engine, "model": model}


@router.delete("/external-chats/{chat_id}")
def delete_chat(chat_id: str):
    items = _load_all()
    n_before = len(items)
    items = [it for it in items if it.get("id") != chat_id]
    if len(items) == n_before:
        raise HTTPException(404, "not found")
    _write_all(items)
    return {"ok": True, "remaining": len(items)}
