"""
GET/POST /api/training/progress — Training progress tracking.

Stores per-exercise checkbox states + body metrics + notes per date.
Pure storage — exercise data lives in the frontend (training-data.ts).
"""

from fastapi import APIRouter
from pydantic import BaseModel

from data_manager import (
    append_jsonl,
    read_jsonl,
    TRAINING_PROGRESS_FILE,
    timestamp_jst,
    now_jst,
)

router = APIRouter()


class ProgressUpdate(BaseModel):
    checked_items: dict[str, bool] = {}
    current_phase: int | None = None
    weight: float | None = None
    body_fat: float | None = None
    notes: str | None = None


def _load_state() -> dict:
    """Reduce log to current state."""
    state = {
        "checked_items": {},
        "current_phase": 0,
        "logs": [],
    }
    for entry in read_jsonl(TRAINING_PROGRESS_FILE):
        if entry.get("type") == "checkbox_update":
            for k, v in entry.get("checked_items", {}).items():
                state["checked_items"][k] = v
        elif entry.get("type") == "phase_change":
            state["current_phase"] = entry.get("current_phase", 0)
        elif entry.get("type") == "log":
            state["logs"].append({
                "date": entry.get("date"),
                "weight": entry.get("weight"),
                "body_fat": entry.get("body_fat"),
                "notes": entry.get("notes"),
                "timestamp": entry.get("timestamp"),
            })
    return state


@router.get("/training/progress")
def get_progress():
    return _load_state()


@router.post("/training/progress")
def update_progress(req: ProgressUpdate):
    now = timestamp_jst()
    today = now_jst().strftime("%Y-%m-%d")

    if req.checked_items:
        append_jsonl(TRAINING_PROGRESS_FILE, {
            "type": "checkbox_update",
            "checked_items": req.checked_items,
            "timestamp": now,
        })

    if req.current_phase is not None:
        append_jsonl(TRAINING_PROGRESS_FILE, {
            "type": "phase_change",
            "current_phase": req.current_phase,
            "timestamp": now,
        })

    if req.weight is not None or req.body_fat is not None or req.notes:
        append_jsonl(TRAINING_PROGRESS_FILE, {
            "type": "log",
            "date": today,
            "weight": req.weight,
            "body_fat": req.body_fat,
            "notes": req.notes,
            "timestamp": now,
        })

    return _load_state()
