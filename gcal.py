"""
Koach OS v2 — Google Calendar Integration
============================================
Read-only Google Calendar access for daily briefing and context injection.

Setup: Run `python scripts/setup_gcal.py` once to authorize.
"""

from pathlib import Path
from datetime import timedelta
from data_manager import BASE_DIR, now_jst, JST

CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def is_configured() -> bool:
    """Check if Google Calendar is set up."""
    return TOKEN_FILE.exists()


def _get_service():
    """Build the Google Calendar API service."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def get_events(days_ahead: int = 0) -> list[dict]:
    """Get events for today (days_ahead=0) or upcoming days.

    Returns list of {summary, start, end, location, description}.
    """
    if not is_configured():
        return []

    try:
        service = _get_service()
    except Exception:
        return []

    now = now_jst()
    target = now + timedelta(days=days_ahead)
    start_of_day = target.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target.replace(hour=23, minute=59, second=59, microsecond=0)

    try:
        result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception:
        return []

    events = []
    for e in result.get("items", []):
        start_raw = e.get("start", {}).get("dateTime", e.get("start", {}).get("date", ""))
        end_raw = e.get("end", {}).get("dateTime", e.get("end", {}).get("date", ""))
        events.append({
            "summary": e.get("summary", "(no title)"),
            "start": start_raw,
            "end": end_raw,
            "location": e.get("location", ""),
            "description": e.get("description", ""),
            "all_day": "T" not in start_raw,
        })
    return events


def get_week_events() -> list[dict]:
    """Get events for the next 7 days."""
    all_events = []
    for d in range(7):
        for e in get_events(days_ahead=d):
            e["day_offset"] = d
            all_events.append(e)
    return all_events


def get_calendar_context() -> str:
    """Format today's events for system prompt injection."""
    events = get_events(days_ahead=0)
    if not events:
        return ""

    now = now_jst()
    lines = [f"TODAY'S SCHEDULE ({now.strftime('%Y-%m-%d %A')}):"]
    for e in events:
        if e["all_day"]:
            time_str = "All day"
        else:
            time_str = e["start"][11:16] if len(e["start"]) > 11 else "?"
        summary = e["summary"]
        loc = f" @ {e['location']}" if e["location"] else ""
        lines.append(f"  - {time_str}: {summary}{loc}")

    # Check if late evening
    if now.hour >= 21:
        lines.append("  NOTE: It is past 9 PM. Protect family/rest time.")

    return "\n".join(lines)


def format_events_html(events: list[dict]) -> str:
    """Format events as HTML for Streamlit display."""
    if not events:
        return '<div style="color:#64748b; font-size:12px;">No events today</div>'

    parts = []
    for e in events:
        if e["all_day"]:
            time_str = "All day"
        else:
            time_str = e["start"][11:16] if len(e["start"]) > 11 else ""
        loc = f' <span style="color:#64748b;">@ {e["location"]}</span>' if e["location"] else ""
        parts.append(
            f'<div style="font-size:12px; padding:3px 0; color:#e2e8f0;">'
            f'<span style="color:#3b82f6; font-family:\'JetBrains Mono\',monospace; min-width:50px; display:inline-block;">{time_str}</span> '
            f'{e["summary"]}{loc}</div>'
        )
    return "".join(parts)
