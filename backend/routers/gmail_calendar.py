"""
GET /api/gmail/recent — fetch recent emails
POST /api/gmail/extract-events — Gemini analyzes emails and proposes calendar events
POST /api/calendar/create-event — create a calendar event
POST /api/gmail/auto-sync — full pipeline: fetch → extract → return proposals
"""

import asyncio
import io
import json
import re
from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from gcal import (
    is_configured,
    list_recent_emails,
    list_recent_emails_all_accounts,
    list_upcoming_events,
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
def gmail_recent(
    days: int = Query(3, ge=1, le=365),
    limit: int = Query(20, ge=1, le=200),
    slot: int = Query(0, ge=0, le=9),  # 0 = all configured slots, otherwise specific slot
):
    """Fetch recent emails. slot=0 fetches all accounts; slot=N fetches that account only."""
    if not is_configured():
        raise HTTPException(status_code=400, detail="Google integration not configured")
    try:
        if slot == 0:
            emails = list_recent_emails_all_accounts(days=days, max_results=limit)
        else:
            emails = list_recent_emails(days=days, max_results=limit, slot=slot)
        return {"emails": emails, "count": len(emails)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail fetch failed: {e}")


@router.get("/gmail/slots")
def gmail_slots():
    """Return list of configured account slots so frontend can chunk fetches per-account."""
    from gcal import _configured_slots
    return {"slots": _configured_slots()}


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


class ExtractFromEmailsRequest(BaseModel):
    """Accept a pre-fetched batch of emails for analysis. Frontend chunks long-range fetches."""
    emails: list[dict]
    engine: str = "gemini"
    model: str | None = None


BATCH_SIZE = 15  # emails per AI call — keeps each call under ~30s


def _build_system_prompt(today_str: str) -> str:
    return f"""You extract calendar event candidates and reminders from emails.

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


def _process_batch(batch_emails: list, system_prompt: str, engine: str, model: str) -> tuple[list, str | None, str | None]:
    """Synchronous batch processor — runs in thread pool. Returns (normalized_proposals, parse_error, raw_preview)."""
    emails_text = "\n\n---EMAIL---\n".join(
        f"ID: {e['id']} (account {e.get('_account_slot', 1)})\nFrom: {e['from']}\nSubject: {e['subject']}\nDate: {e['date']}\n\n{e['body'] or e['snippet']}"
        for e in batch_emails
    )
    user_msg = f"Extract calendar events from these emails:\n\n{emails_text}"

    try:
        response = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
            engine=engine,
            model=model,
            max_tokens=8000,
        )
    except Exception as e:
        return [], f"AI call failed: {e}", None

    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

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

    raw_preview = response[:500] if not normalized else None
    return normalized, parse_error, raw_preview


@router.post("/gmail/extract-events")
async def extract_events(req: ExtractRequest):
    """Use Gemini (or other engine) to extract event candidates from recent emails. Batches in parallel for long ranges."""
    if not is_configured():
        raise HTTPException(status_code=400, detail="Google integration not configured")

    try:
        emails = list_recent_emails_all_accounts(days=req.days, max_results=req.limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail fetch failed: {e}")

    if not emails:
        return {"proposals": [], "emails_scanned": 0}

    today_str = now_jst().strftime("%Y-%m-%d (%A)")
    system_prompt = _build_system_prompt(today_str)

    engine = req.engine if req.engine in DEFAULT_MODELS else "gemini"
    model = req.model or DEFAULT_MODELS.get(engine, DEFAULT_MODELS["gemini"])

    batches = [emails[i:i + BATCH_SIZE] for i in range(0, len(emails), BATCH_SIZE)]

    loop = asyncio.get_event_loop()
    results = await asyncio.gather(*[
        loop.run_in_executor(None, _process_batch, b, system_prompt, engine, model)
        for b in batches
    ])

    all_proposals: list = []
    parse_errors: list[str] = []
    raw_previews: list[str] = []
    for props, err, preview in results:
        all_proposals.extend(props)
        if err:
            parse_errors.append(err)
        if preview:
            raw_previews.append(preview)

    # Deduplicate by (title, start_iso) — same event mentioned in multiple emails
    seen = set()
    deduped = []
    for p in all_proposals:
        key = (p["title"], p["start_iso"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(p)

    return {
        "proposals": deduped,
        "emails_scanned": len(emails),
        "batches": len(batches),
        "batch_size": BATCH_SIZE,
        "engine_used": engine,
        "model_used": model,
        "ai_raw_preview": raw_previews[0] if raw_previews and not deduped else None,
        "parse_error": "; ".join(parse_errors) if parse_errors else None,
    }


@router.post("/gmail/extract-events-from-emails")
def extract_events_from_emails(req: ExtractFromEmailsRequest):
    """Analyze a pre-fetched batch of emails. Frontend uses this for long-range chunked processing."""
    if not req.emails:
        return {"proposals": [], "emails_scanned": 0}

    today_str = now_jst().strftime("%Y-%m-%d (%A)")
    system_prompt = _build_system_prompt(today_str)
    engine = req.engine if req.engine in DEFAULT_MODELS else "gemini"
    model = req.model or DEFAULT_MODELS.get(engine, DEFAULT_MODELS["gemini"])

    proposals, parse_error, raw_preview = _process_batch(req.emails, system_prompt, engine, model)

    return {
        "proposals": proposals,
        "emails_scanned": len(req.emails),
        "engine_used": engine,
        "model_used": model,
        "ai_raw_preview": raw_preview if not proposals else None,
        "parse_error": parse_error,
    }


@router.post("/calendar/extract-events-from-pdf")
async def extract_events_from_pdf(
    file: UploadFile = File(...),
    engine: str = "gemini",
):
    """Extract calendar candidates from an uploaded PDF (日程表・年間予定表 etc.)."""
    try:
        from PyPDF2 import PdfReader
    except ImportError:
        raise HTTPException(status_code=500, detail="PyPDF2 not available")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="empty file")

    try:
        reader = PdfReader(io.BytesIO(contents))
        text_pages = []
        for p in reader.pages:
            try:
                text_pages.append(p.extract_text() or "")
            except Exception:
                text_pages.append("")
        full_text = "\n\n---PAGE---\n\n".join(text_pages)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"PDF parse failed: {e}")

    if not full_text.strip():
        return {
            "proposals": [],
            "parse_error": "PDF からテキストを抽出できませんでした（画像のみ・スキャンPDF の可能性）",
            "filename": file.filename,
            "page_count": len(text_pages),
        }

    today_str = now_jst().strftime("%Y-%m-%d (%A)")
    system_prompt = f"""You extract calendar events from a document (schedule sheet, syllabus, meeting agenda).

TODAY IS: {today_str}

The text comes from a PDF — may contain table-formatted dates, semester schedules, exam schedules, committee schedules.

Items to extract:
- All meetings, classes, exams, committees, deadlines with dates/times
- All-day events if no time specified
- Multi-day events as separate entries OR one entry with start/end spanning the range (your choice based on context)

Output rules:
- Output ONLY a JSON array. No markdown, no commentary.
- Each item: {{title, start_iso, end_iso, description, location, confidence, event_type, source_email_id, source_subject}}
- ISO 8601 with timezone (+09:00) or all-day "YYYY-MM-DD"
- source_email_id: leave "" (it's from PDF, not email)
- source_subject: use the document filename or section header
- event_type: meeting/committee/deadline/default
- title: in Japanese if source is Japanese
- If a year is omitted, assume the most likely year given today's date

Return [] only if no dates can be identified."""

    user_msg = f"Extract calendar events from this PDF text (filename: {file.filename}):\n\n{full_text[:80000]}"
    selected_engine = engine if engine in DEFAULT_MODELS else "gemini"
    model = DEFAULT_MODELS.get(selected_engine, DEFAULT_MODELS["gemini"])

    # Reuse _process_batch's parsing logic by calling AI inline (text is one big "email")
    fake_batch = [{
        "id": "pdf",
        "from": file.filename or "uploaded.pdf",
        "subject": file.filename or "PDF",
        "date": today_str,
        "body": full_text[:80000],
        "snippet": "",
        "_account_slot": 0,
    }]
    # _process_batch builds its own emails_text — but we need a custom prompt. Inline the call:
    try:
        response = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
            engine=selected_engine,
            model=model,
            max_tokens=8000,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI extraction failed: {e}")

    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
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
            "source_email_id": "",
            "source_subject": file.filename or "PDF",
        })

    return {
        "proposals": normalized,
        "filename": file.filename,
        "page_count": len(text_pages),
        "engine_used": selected_engine,
        "model_used": model,
        "parse_error": parse_error,
        "ai_raw_preview": response[:500] if not normalized else None,
    }


@router.get("/calendar/upcoming")
def calendar_upcoming(days_ahead: int = Query(7, ge=1, le=60)):
    """Read upcoming events from Google Calendar (the source of truth)."""
    if not is_configured():
        raise HTTPException(status_code=400, detail="Google integration not configured")
    try:
        events = list_upcoming_events(days_ahead=days_ahead)
        return {"events": events, "count": len(events)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar read failed: {e}")


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
