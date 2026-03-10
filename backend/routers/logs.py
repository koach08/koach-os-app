"""
GET /api/logs — Log browser with filters.
"""

from fastapi import APIRouter, Query
from data_manager import read_jsonl, export_jsonl, LOGS_FILE, get_recent_logs

router = APIRouter()


@router.get("/logs")
def get_logs(
    domain: str | None = Query(None),
    level: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
):
    """Get interaction logs with optional filters."""
    logs = get_recent_logs(limit)

    if domain:
        logs = [l for l in logs if l.get("domain") == domain]
    if level:
        logs = [l for l in logs if l.get("intervention_level") == level]
    if search:
        s = search.lower()
        logs = [
            l for l in logs
            if s in l.get("user_input_preview", "").lower()
            or s in l.get("ai_response_preview", "").lower()
        ]

    return {"logs": logs, "total": len(logs)}


@router.get("/logs/export")
def export_logs():
    """Export raw JSONL data."""
    content = export_jsonl(LOGS_FILE)
    return {"content": content, "filename": "interaction_logs.jsonl"}
