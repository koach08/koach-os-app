"""
Completion log — mark today's calendar events / backlog tasks as done from Daily Brief.

Storage: append-only JSONL at data/completions.jsonl, tombstoned with _deleted entries.
Each completion ties to a (kind, ref_id, date) tuple so re-checking the same event the
same day is idempotent and unchecking is one DELETE call.
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data_manager import (
    DATA_DIR,
    append_jsonl,
    init_jsonl,
    read_jsonl,
    now_jst,
    timestamp_jst,
)

router = APIRouter()

COMPLETIONS_FILE = DATA_DIR / "completions.jsonl"
init_jsonl(COMPLETIONS_FILE, "completion", "Daily Brief check-off log")

Kind = Literal["calendar", "backlog"]


class CompletionIn(BaseModel):
    kind: Kind = "calendar"
    ref_id: str
    title: str = ""
    date: str = ""  # YYYY-MM-DD; defaults to today JST
    category: str = ""  # optional, copied from backlog/event
    note: str = ""


def _today_jst() -> str:
    return now_jst().strftime("%Y-%m-%d")


def _current_state() -> dict[tuple[str, str, str], dict]:
    """Replay the JSONL into a map keyed by (kind, ref_id, date).

    Tombstones (`_deleted: true`) remove the matching key.
    """
    state: dict[tuple[str, str, str], dict] = {}
    for entry in read_jsonl(COMPLETIONS_FILE):
        kind = entry.get("kind", "calendar")
        ref_id = entry.get("ref_id", "")
        date = entry.get("date", "")
        if not ref_id or not date:
            continue
        key = (kind, ref_id, date)
        if entry.get("_deleted"):
            state.pop(key, None)
        else:
            state[key] = entry
    return state


@router.get("/completions")
def list_completions(
    date: str = Query("", description="YYYY-MM-DD, defaults to today JST"),
    kind: str = Query("", description="optional filter: calendar / backlog"),
):
    target_date = date or _today_jst()
    state = _current_state()
    items = [
        v for (k, _ref, d), v in state.items()
        if d == target_date and (not kind or k == kind)
    ]
    items.sort(key=lambda x: x.get("completed_at", ""))
    return {"date": target_date, "items": items}


@router.post("/completions")
def add_completion(payload: CompletionIn):
    target_date = payload.date or _today_jst()
    # sanity-check date format
    try:
        date_cls.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    if not payload.ref_id:
        raise HTTPException(status_code=400, detail="ref_id required")

    entry = {
        "kind": payload.kind,
        "ref_id": payload.ref_id,
        "title": payload.title,
        "date": target_date,
        "category": payload.category,
        "note": payload.note,
        "completed_at": timestamp_jst(),
    }
    append_jsonl(COMPLETIONS_FILE, entry)
    return entry


@router.delete("/completions")
def remove_completion(
    ref_id: str = Query(..., description="event/backlog ID"),
    kind: str = Query("calendar"),
    date: str = Query("", description="YYYY-MM-DD, defaults to today JST"),
):
    target_date = date or _today_jst()
    state = _current_state()
    key = (kind, ref_id, target_date)
    if key not in state:
        return {"ok": True, "removed": False}
    tombstone = {
        "kind": kind,
        "ref_id": ref_id,
        "date": target_date,
        "_deleted": True,
        "deleted_at": timestamp_jst(),
    }
    append_jsonl(COMPLETIONS_FILE, tombstone)
    return {"ok": True, "removed": True}
