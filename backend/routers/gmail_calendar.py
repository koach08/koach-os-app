"""
GET /api/gmail/recent — fetch recent emails
POST /api/gmail/extract-events — Gemini analyzes emails and proposes calendar events
POST /api/calendar/create-event — create a calendar event
POST /api/gmail/auto-sync — full pipeline: fetch → extract → return proposals
"""

import json
import re
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from gcal import (
    is_configured,
    list_recent_emails,
    list_recent_emails_all_accounts,
    create_event as gcal_create_event,
)
from data_manager import now_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()


@router.get("/gmail/status")
def gmail_status():
    """Check if Google integration (Gmail + Calendar write) is configured."""
    return {"configured": is_configured()}


@router.get("/gmail/recent")
def gmail_recent(days: int = Query(3, ge=1, le=365), limit: int = Query(20, ge=1, le=200)):
    """Fetch recent emails."""
    if not is_configured():
        raise HTTPException(status_code=400, detail="Google integration not configured")
    try:
        emails = list_recent_emails_all_accounts(days=days, max_results=limit)
        return {"emails": emails, "count": len(emails)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail fetch failed: {e}")


class ExtractRequest(BaseModel):
    days: int = 3
    limit: int = 20
    engine: str = "gemini"  # default: Gemini for long context
    model: str | None = None

    def model_post_init(self, _ctx):
        if self.days < 1:
            self.days = 1
        if self.days > 365:
            self.days = 365
        if self.limit < 1:
            self.limit = 1
        if self.limit > 200:
            self.limit = 200


class EventProposal(BaseModel):
    title: str
    start_iso: str
    end_iso: str
    description: str = ""
    location: str = ""
    confidence: str = "medium"  # high/medium/low
    event_type: str = "default"  # meeting/committee/deadline/default
    source_email_id: str = ""
    source_subject: str = ""


@router.post("/gmail/extract-events")
def extract_events(req: ExtractRequest):
    """Use Gemini (or other engine) to extract event candidates from recent emails."""
    if not is_configured():
        raise HTTPException(status_code=400, detail="Google integration not configured")

    try:
        emails = list_recent_emails_all_accounts(days=req.days, max_results=req.limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail fetch failed: {e}")

    if not emails:
        return {"proposals": [], "emails_scanned": 0}

    # Build prompt for the AI (include account slot for traceability)
    emails_text = "\n\n---EMAIL---\n".join(
        f"ID: {e['id']} (account {e.get('_account_slot', 1)})\nFrom: {e['from']}\nSubject: {e['subject']}\nDate: {e['date']}\n\n{e['body'] or e['snippet']}"
        for e in emails
    )

    # Current date for context (helps avoid mis-classifying recent past as old)
    today_str = now_jst().strftime("%Y-%m-%d (%A)")

    system_prompt = f"""You extract calendar event candidates and reminders from emails.

TODAY IS: {today_str}

Be GENEROUS in extracting — better to over-include than miss something.
Items to extract:
- Meetings, committees, classes, exams (会議・委員会・授業・試験)
- Deadlines, due dates, submission requests (締切・提出期限)
- Appointments, interviews, calls (面談・面接)
- Reminders about ongoing things (進行中の試験運用変更・連絡事項) — even if no explicit future date, include as confidence=low with today's date
- Travel, flights, reservations
- ANY mention of a specific date or time someone needs to attend / submit / do something

DO include events from the recent past if the email talks about ongoing situations
(e.g., "中間試験中の入室キーワード" relates to an ongoing exam period — include it).

Output rules:
- Output ONLY a JSON array. No markdown, no commentary.
- Each item: {{title, start_iso, end_iso, description, location, confidence, event_type, source_email_id, source_subject}}
- Use ISO 8601 with timezone (e.g., "2026-05-15T14:00:00+09:00") OR all-day "YYYY-MM-DD"
- Default timezone: Asia/Tokyo (+09:00)
- If only an approximate date is mentioned (今週中, 来週など), set confidence=low and pick a reasonable date
- confidence: "high" (explicit date/time), "medium" (inferred), "low" (vague or implicit)
- event_type:
    "meeting" — 会議・打ち合わせ・面談・授業
    "committee" — 委員会・理事会・審議会
    "deadline" — 締め切り・提出期限・due
    "default" — リマインダー、その他
- SKIP only obvious marketing/spam (Skyscanner deals, Amazon promos, newsletters with no specific user action)
- title: concise, in the email's language (Japanese stays Japanese)
- If multiple events in one email, output multiple entries

Return [] only if absolutely nothing actionable. When in doubt, INCLUDE."""

    user_msg = f"Extract calendar events from these emails:\n\n{emails_text}"

    engine = req.engine if req.engine in DEFAULT_MODELS else "gemini"
    model = req.model or DEFAULT_MODELS.get(engine, DEFAULT_MODELS["gemini"])

    try:
        response = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
            engine=engine,
            model=model,
            max_tokens=8000,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI extraction failed: {e}")

    # Parse JSON (be tolerant of markdown code fences)
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    # Sometimes AI wraps JSON in extra text — find first [ and last ]
    if not cleaned.startswith("["):
        first = cleaned.find("[")
        last = cleaned.rfind("]")
        if first != -1 and last != -1 and last > first:
            cleaned = cleaned[first:last + 1]

    parse_error = None
    try:
        proposals = json.loads(cleaned)
        if not isinstance(proposals, list):
            proposals = []
    except json.JSONDecodeError as e:
        proposals = []
        parse_error = str(e)

    # Normalize each proposal
    normalized = []
    for p in proposals:
        if not isinstance(p, dict):
            continue
        normalized.append({
            "title": str(p.get("title", ""))[:200],
            "start_iso": str(p.get("start_iso", "")),
            "end_iso": str(p.get("end_iso", "")),
            "description": str(p.get("description", ""))[:500],
            "location": str(p.get("location", ""))[:200],
            "confidence": p.get("confidence", "medium"),
            "event_type": p.get("event_type", "default"),
            "source_email_id": str(p.get("source_email_id", "")),
            "source_subject": str(p.get("source_subject", ""))[:200],
        })

    return {
        "proposals": normalized,
        "emails_scanned": len(emails),
        "engine_used": engine,
        "model_used": model,
        "ai_raw_preview": response[:500] if not normalized else None,
        "parse_error": parse_error,
    }


class CreateEventRequest(BaseModel):
    title: str
    start_iso: str
    end_iso: str
    description: str = ""
    location: str = ""
    event_type: str | None = None  # meeting/committee/deadline/default; auto-detect if None


@router.post("/calendar/create-event")
def create_event(req: CreateEventRequest):
    """Create a Google Calendar event with type-aware reminders."""
    if not is_configured():
        raise HTTPException(status_code=400, detail="Google integration not configured")
    try:
        result = gcal_create_event(
            title=req.title,
            start_iso=req.start_iso,
            end_iso=req.end_iso,
            description=req.description,
            location=req.location,
            event_type=req.event_type,
        )
        return {
            "id": result.get("id", ""),
            "html_link": result.get("htmlLink", ""),
            "status": result.get("status", ""),
            "event_type_used": result.get("_event_type_used", "default"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar event creation failed: {e}")
