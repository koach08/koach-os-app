"""
集中タイマー — Pomodoro 風の 25/50/90 分セッション。
完了で focus_sessions.jsonl に追記、completions と同じく Daily Brief に反映。

API:
  POST /api/focus/start  { task, category, planned_minutes }
  POST /api/focus/stop   { session_id, actual_minutes?, note? }
  GET  /api/focus/active
  GET  /api/focus/today
  GET  /api/focus/week
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import DATA_DIR, append_jsonl, init_jsonl, read_jsonl, now_jst, timestamp_jst

router = APIRouter()

SESSIONS_FILE = DATA_DIR / "focus_sessions.jsonl"
ACTIVE_FILE = DATA_DIR / "focus_active.json"
init_jsonl(SESSIONS_FILE, "focus_session", "Pomodoro / focus block log")


Category = Literal[
    "career", "research", "creative", "family", "health",
    "learning", "side_project", "admin", "rest", "other",
]


class StartReq(BaseModel):
    task: str
    category: Category = "other"
    planned_minutes: int = 25


class StopReq(BaseModel):
    session_id: str
    actual_minutes: int | None = None
    note: str = ""
    completed: bool = True


def _write_active(data: dict | None):
    if data is None:
        if ACTIVE_FILE.exists():
            ACTIVE_FILE.unlink()
        return
    ACTIVE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _read_active() -> dict | None:
    if not ACTIVE_FILE.exists():
        return None
    try:
        return json.loads(ACTIVE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return None


@router.post("/focus/start")
def focus_start(req: StartReq):
    if _read_active():
        raise HTTPException(status_code=409, detail="既に集中セッション中。先に stop してください")
    now = now_jst()
    session = {
        "session_id": f"fs_{int(now.timestamp() * 1000)}",
        "task": req.task,
        "category": req.category,
        "planned_minutes": max(1, min(180, req.planned_minutes)),
        "started_at": now.isoformat(),
    }
    _write_active(session)
    return session


@router.post("/focus/stop")
def focus_stop(req: StopReq):
    active = _read_active()
    if not active or active.get("session_id") != req.session_id:
        raise HTTPException(status_code=404, detail="該当セッションが見つかりません")
    now = now_jst()
    from datetime import datetime as dt
    try:
        started = dt.fromisoformat(active["started_at"])
        elapsed = max(1, int((now - started).total_seconds() / 60))
    except Exception:
        elapsed = req.actual_minutes or active["planned_minutes"]
    actual = req.actual_minutes or elapsed
    entry = {
        **active,
        "ended_at": now.isoformat(),
        "actual_minutes": actual,
        "note": req.note,
        "completed": req.completed,
        "date": now.strftime("%Y-%m-%d"),
    }
    append_jsonl(SESSIONS_FILE, entry)
    _write_active(None)
    return entry


@router.get("/focus/active")
def focus_active():
    a = _read_active()
    return {"active": a}


@router.get("/focus/today")
def focus_today():
    today = now_jst().strftime("%Y-%m-%d")
    sessions = [s for s in read_jsonl(SESSIONS_FILE) if s.get("date") == today]
    total = sum(s.get("actual_minutes", 0) for s in sessions if s.get("completed"))
    by_cat: dict[str, int] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        c = s.get("category", "other")
        by_cat[c] = by_cat.get(c, 0) + s.get("actual_minutes", 0)
    return {
        "date": today,
        "sessions": sessions,
        "total_minutes": total,
        "by_category": by_cat,
    }


@router.get("/focus/week")
def focus_week():
    from datetime import timedelta
    now = now_jst()
    cutoff = (now.date() - timedelta(days=6)).isoformat()
    sessions = [s for s in read_jsonl(SESSIONS_FILE) if s.get("date", "") >= cutoff]
    by_day: dict[str, dict] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        d = s.get("date", "")
        if d not in by_day:
            by_day[d] = {"total_minutes": 0, "by_category": {}}
        by_day[d]["total_minutes"] += s.get("actual_minutes", 0)
        c = s.get("category", "other")
        by_day[d]["by_category"][c] = by_day[d]["by_category"].get(c, 0) + s.get("actual_minutes", 0)
    by_cat_total: dict[str, int] = {}
    for s in sessions:
        if not s.get("completed"):
            continue
        c = s.get("category", "other")
        by_cat_total[c] = by_cat_total.get(c, 0) + s.get("actual_minutes", 0)
    return {
        "since": cutoff,
        "by_day": by_day,
        "by_category_total": by_cat_total,
        "session_count": sum(1 for s in sessions if s.get("completed")),
    }
