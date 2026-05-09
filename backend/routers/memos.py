"""
GET/POST/PATCH/DELETE /api/memos — Sticky-note memos.

Append-only log; latest entry per id wins. Same pattern as tasks.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import (
    append_jsonl,
    read_jsonl,
    MEMOS_FILE,
    generate_id,
    timestamp_jst,
)

router = APIRouter()

VALID_COLORS = {"yellow", "blue", "green", "pink"}


def _materialize() -> dict[str, dict]:
    state: dict[str, dict] = {}
    for e in read_jsonl(MEMOS_FILE):
        mid = e.get("id")
        if not mid:
            continue
        if e.get("_deleted"):
            state.pop(mid, None)
            continue
        state[mid] = e
    return state


class MemoCreate(BaseModel):
    content: str
    color: str = "yellow"
    pinned: bool = False


class MemoUpdate(BaseModel):
    content: str | None = None
    color: str | None = None
    pinned: bool | None = None


@router.get("/memos")
def list_memos():
    state = _materialize()
    memos = list(state.values())
    # Pinned first, then newest first
    memos.sort(key=lambda m: (not m.get("pinned", False), -float(m.get("created_at_ts", 0))))
    return {"memos": memos, "count": len(memos)}


@router.post("/memos")
def create_memo(req: MemoCreate):
    if req.color not in VALID_COLORS:
        raise HTTPException(400, f"color must be one of {VALID_COLORS}")

    now = timestamp_jst()
    memo = {
        "id": generate_id("memo"),
        "content": req.content,
        "color": req.color,
        "pinned": req.pinned,
        "created_at": now,
        "created_at_ts": _ts(now),
        "updated_at": now,
    }
    append_jsonl(MEMOS_FILE, memo)
    return memo


@router.patch("/memos/{memo_id}")
def update_memo(memo_id: str, req: MemoUpdate):
    current = _materialize().get(memo_id)
    if not current:
        raise HTTPException(404, "Memo not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "color" in updates and updates["color"] not in VALID_COLORS:
        raise HTTPException(400, f"color must be one of {VALID_COLORS}")

    new = {**current, **updates, "updated_at": timestamp_jst()}
    append_jsonl(MEMOS_FILE, new)
    return new


@router.delete("/memos/{memo_id}")
def delete_memo(memo_id: str):
    if not _materialize().get(memo_id):
        raise HTTPException(404, "Memo not found")
    append_jsonl(MEMOS_FILE, {"id": memo_id, "_deleted": True, "deleted_at": timestamp_jst()})
    return {"deleted": True, "id": memo_id}


def _ts(iso: str) -> float:
    """Convert ISO string to unix timestamp for sorting."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return 0.0
