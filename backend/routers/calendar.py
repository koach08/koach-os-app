"""
GET /api/calendar — Google Calendar events + daily briefing.
"""

from fastapi import APIRouter
from gcal import is_configured, get_events, get_week_events, get_calendar_context
from router import call_ai, DEFAULT_MODELS
from data_manager import read_jsonl, LOGS_FILE, now_jst

router = APIRouter()


@router.get("/calendar/status")
def calendar_status():
    """Check if Google Calendar is configured."""
    return {"configured": is_configured()}


@router.get("/calendar/today")
def today_events():
    """Get today's events."""
    if not is_configured():
        return {"events": [], "configured": False}
    return {"events": get_events(days_ahead=0), "configured": True}


@router.get("/calendar/week")
def week_events():
    """Get this week's events."""
    if not is_configured():
        return {"events": [], "configured": False}
    return {"events": get_week_events(), "configured": True}


@router.get("/calendar/visible")
def visible_calendars():
    """全 slot で backend が見えている calendar 一覧 (debug 用)。"""
    if not is_configured():
        return {"configured": False, "sources": []}
    from gcal import _all_visible_calendar_sources, _get_service
    out = []
    for slot, cid in _all_visible_calendar_sources():
        meta = {"slot": slot, "calendar_id": cid, "summary": cid, "primary": cid == "primary"}
        try:
            service = _get_service(slot)
            info = service.calendarList().get(calendarId=cid).execute()
            meta["summary"] = info.get("summary") or info.get("summaryOverride") or cid
            meta["description"] = info.get("description", "")
            meta["timezone"] = info.get("timeZone", "")
        except Exception:
            pass
        out.append(meta)
    return {"configured": True, "sources": out, "count": len(out)}


@router.get("/calendar/family")
def family_events(days_ahead: int = 7):
    """EXTRA_CALENDAR_IDS で指定された家族 calendar の予定。"""
    if not is_configured():
        return {"events": [], "configured": False}
    from datetime import timedelta
    from gcal import list_family_events_range, _extra_calendar_ids
    now = now_jst()
    start = now.strftime("%Y-%m-%d")
    end = (now + timedelta(days=days_ahead + 1)).strftime("%Y-%m-%d")
    return {
        "events": list_family_events_range(start, end),
        "configured": True,
        "calendar_ids": _extra_calendar_ids(),
    }


@router.get("/calendar/briefing")
def daily_briefing():
    """Generate an AI-powered daily briefing based on calendar + recent activity."""
    now = now_jst()
    cal_context = get_calendar_context() if is_configured() else "Calendar not connected."

    # Get recent logs for context
    logs = read_jsonl(LOGS_FILE)
    recent = logs[-10:] if logs else []
    recent_topics = [
        log.get("user_input_preview", "")
        for log in recent
        if log.get("user_input_preview")
    ]

    prompt = f"""You are Koach OS, a personal AI advisor. Generate a concise daily briefing in Japanese.

Current time: {now.strftime('%Y-%m-%d %H:%M (%A)')}

{cal_context}

Recent conversation topics:
{chr(10).join(f'- {t}' for t in recent_topics[-5:]) if recent_topics else '(no recent conversations)'}

Generate a brief (3-5 bullet points) covering:
1. Today's schedule overview and any urgent items
2. Reminders based on recent conversations (things that might be forgotten)
3. One suggestion for what to prioritize today
4. Any warnings (time conflicts, overcommitting, etc.)

Keep it casual and direct, like a trusted advisor would speak."""

    try:
        response = call_ai(
            messages=[{"role": "user", "content": "Daily briefing please."}],
            system=prompt,
            engine="claude",
            model=DEFAULT_MODELS["claude"],
            max_tokens=500,
        )
        return {"briefing": response, "time": now.isoformat()}
    except Exception as e:
        return {"briefing": f"Briefing generation failed: {e}", "time": now.isoformat()}
