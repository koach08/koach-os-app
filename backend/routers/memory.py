"""
GET/POST /api/memory — Memory management (heuristics, decisions, failures, voice, feedback).
"""

from fastapi import APIRouter
from pydantic import BaseModel
from data_manager import (
    read_jsonl, append_jsonl, read_yaml, update_yaml,
    DECISIONS_FILE, FAILURES_FILE, FEEDBACK_FILE, VOICE_FILE,
    HEURISTICS_FILE, EXPERIENCES_FILE,
    generate_id, timestamp_jst,
)

router = APIRouter()


@router.get("/memory/heuristics")
def get_heuristics():
    """Get current heuristics (rules of thumb)."""
    return read_yaml(HEURISTICS_FILE)


@router.get("/memory/decisions")
def get_decisions():
    """Get decision log."""
    return {"entries": read_jsonl(DECISIONS_FILE)}


@router.get("/memory/failures")
def get_failures():
    """Get failure log."""
    return {"entries": read_jsonl(FAILURES_FILE)}


@router.get("/memory/voice")
def get_voice():
    """Get voice profile observations."""
    return {"entries": read_jsonl(VOICE_FILE)}


@router.get("/memory/feedback")
def get_feedback():
    """Get feedback patterns."""
    return {"entries": read_jsonl(FEEDBACK_FILE)}


@router.get("/memory/experiences")
def get_experiences():
    """Get experiences."""
    return {"entries": read_jsonl(EXPERIENCES_FILE)}


class DecisionEntry(BaseModel):
    title: str
    context: str
    options: list[str] = []
    chosen: str = ""
    reasoning: str = ""
    domain: str = "personal"


@router.post("/memory/decisions")
def add_decision(entry: DecisionEntry):
    """Log a key decision."""
    record = {
        "id": generate_id("dec"),
        "timestamp": timestamp_jst(),
        **entry.model_dump(),
    }
    append_jsonl(DECISIONS_FILE, record)
    return record


class FailureEntry(BaseModel):
    what_happened: str
    why: str = ""
    lesson: str = ""
    domain: str = "personal"


@router.post("/memory/failures")
def add_failure(entry: FailureEntry):
    """Log a failure with lesson learned."""
    record = {
        "id": generate_id("fail"),
        "timestamp": timestamp_jst(),
        **entry.model_dump(),
    }
    append_jsonl(FAILURES_FILE, record)
    return record
