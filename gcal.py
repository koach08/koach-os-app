"""
Koach OS v2 — Google Calendar + Gmail Integration
====================================================
- Calendar: read + write (events insert)
- Gmail: read-only

Setup:
  Local: Run `python scripts/setup_gcal.py` once to authorize and create token.json
  Railway: Set env var GOOGLE_TOKEN_JSON with the contents of token.json
"""

import json
from pathlib import Path
from datetime import timedelta
from data_manager import BASE_DIR, now_jst, JST, get_secret

CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"

# Expanded scope: calendar full access (read+write) + gmail read-only
SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
]


REMINDER_PRESETS = {
    "meeting": [
        {"method": "popup", "minutes": 30},
        {"method": "popup", "minutes": 1440},  # 1 day before
    ],
    "committee": [
        {"method": "popup", "minutes": 60},
        {"method": "popup", "minutes": 1440},
        {"method": "email", "minutes": 1440},
    ],
    "deadline": [
        {"method": "popup", "minutes": 1440},      # 1 day before
        {"method": "popup", "minutes": 4320},      # 3 days before
        {"method": "email", "minutes": 10080},     # 1 week before
    ],
    "default": [
        {"method": "popup", "minutes": 15},
    ],
}


def _token_env_name(slot: int) -> str:
    """slot 1 = GOOGLE_TOKEN_JSON, slot 2 = GOOGLE_TOKEN_JSON_2, ..."""
    return "GOOGLE_TOKEN_JSON" if slot == 1 else f"GOOGLE_TOKEN_JSON_{slot}"


def _token_file_path(slot: int):
    """slot 1 = token.json, slot 2 = token_2.json, ..."""
    return TOKEN_FILE if slot == 1 else TOKEN_FILE.parent / f"token_{slot}.json"


def _load_token_dict(slot: int = 1) -> dict | None:
    """Load token from env var (Railway) or local file (dev).
    Tolerates whitespace/newlines that dashboard UIs may insert.
    """
    token_str = get_secret(_token_env_name(slot))
    if token_str:
        # Strip stray whitespace/newlines from dashboard paste
        cleaned = token_str.strip().replace("\r", "").replace("\n", "")
        try:
            return json.loads(cleaned)
        except Exception:
            try:
                return json.loads(token_str)
            except Exception:
                pass
    fp = _token_file_path(slot)
    if fp.exists():
        try:
            return json.loads(fp.read_text())
        except Exception:
            pass
    return None


def _configured_slots(max_slots: int = 5) -> list[int]:
    """Return list of slot numbers (1..N) that have a token configured."""
    return [s for s in range(1, max_slots + 1) if _load_token_dict(s) is not None]


def is_configured() -> bool:
    """Check if at least one Google account is set up."""
    return len(_configured_slots()) > 0


def _get_creds(slot: int = 1):
    """Get Google OAuth credentials for a specific slot."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token_dict = _load_token_dict(slot)
    if not token_dict:
        return None

    creds = Credentials.from_authorized_user_info(token_dict, SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        fp = _token_file_path(slot)
        if fp.exists():
            fp.write_text(creds.to_json())

    return creds


def _get_service(slot: int = 1):
    """Build the Google Calendar API service for a specific slot (default: primary)."""
    from googleapiclient.discovery import build

    creds = _get_creds(slot)
    if not creds:
        raise RuntimeError(f"Google credentials not configured for slot {slot}")
    return build("calendar", "v3", credentials=creds)


def _get_gmail_service(slot: int = 1):
    """Build the Gmail API service for a specific slot."""
    from googleapiclient.discovery import build

    creds = _get_creds(slot)
    if not creds:
        raise RuntimeError(f"Google credentials not configured for slot {slot}")
    return build("gmail", "v1", credentials=creds)


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

    if now.hour >= 21:
        lines.append("  NOTE: It is past 9 PM. Protect family/rest time.")

    return "\n".join(lines)


def detect_event_type(title: str, description: str = "") -> str:
    """Auto-detect event type from title/description for reminder selection."""
    text = (title + " " + description).lower()
    if any(k in text for k in ["deadline", "due", "submit", "提出", "締切", "締め切り", "期限"]):
        return "deadline"
    if any(k in text for k in ["committee", "委員会", "理事会", "審議会", "評議会"]):
        return "committee"
    if any(k in text for k in ["meeting", "会議", "ミーティング", "打ち合わせ", "打合せ", "面談", "会合"]):
        return "meeting"
    return "default"


def create_event(
    title: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
    location: str = "",
    timezone: str = "Asia/Tokyo",
    event_type: str | None = None,
) -> dict:
    """Create a calendar event with type-aware reminders.

    event_type: meeting / committee / deadline / default / None (auto-detect).
    """
    service = _get_service()

    resolved_type = event_type or detect_event_type(title, description)
    reminders = REMINDER_PRESETS.get(resolved_type, REMINDER_PRESETS["default"])

    if len(start_iso) <= 10:  # YYYY-MM-DD all-day
        body = {
            "summary": title,
            "start": {"date": start_iso},
            "end": {"date": end_iso},
            "description": description,
            "location": location,
            "reminders": {"useDefault": False, "overrides": reminders},
        }
    else:
        body = {
            "summary": title,
            "start": {"dateTime": start_iso, "timeZone": timezone},
            "end": {"dateTime": end_iso, "timeZone": timezone},
            "description": description,
            "location": location,
            "reminders": {"useDefault": False, "overrides": reminders},
        }

    result = service.events().insert(calendarId="primary", body=body).execute()
    result["_event_type_used"] = resolved_type
    return result


def list_recent_emails(days: int = 3, max_results: int = 20, slot: int = 1) -> list[dict]:
    """Fetch recent emails from a single slot. Returns list of dicts."""
    service = _get_gmail_service(slot)
    query = f"newer_than:{days}d -in:spam -in:trash"

    listing = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    msg_refs = listing.get("messages", [])

    emails = []
    for ref in msg_refs:
        try:
            msg = service.users().messages().get(
                userId="me", id=ref["id"], format="full"
            ).execute()
            parsed = _parse_message(msg)
            parsed["_account_slot"] = slot
            emails.append(parsed)
        except Exception:
            continue
    return emails


def list_recent_emails_all_accounts(days: int = 3, max_results: int = 20) -> list[dict]:
    """Fetch recent emails from ALL configured accounts. Returns merged list."""
    all_emails: list[dict] = []
    errors: list[str] = []
    for slot in _configured_slots():
        try:
            emails = list_recent_emails(days=days, max_results=max_results, slot=slot)
            all_emails.extend(emails)
        except Exception as e:
            errors.append(f"slot {slot}: {e}")
    # If everything failed, raise the first error so caller sees it
    if not all_emails and errors:
        raise RuntimeError("; ".join(errors))
    return all_emails


def _parse_message(msg: dict) -> dict:
    """Parse Gmail API message into simplified dict."""
    import base64

    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}

    body_text = ""
    payload = msg.get("payload", {})

    def walk(part):
        nonlocal body_text
        mime = part.get("mimeType", "")
        if mime == "text/plain" and not body_text:
            data = part.get("body", {}).get("data", "")
            if data:
                try:
                    body_text = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
                except Exception:
                    pass
        for sub in part.get("parts", []):
            walk(sub)

    walk(payload)
    body_text = body_text[:3000]

    return {
        "id": msg.get("id", ""),
        "from": headers.get("from", ""),
        "subject": headers.get("subject", "(no subject)"),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", "")[:200],
        "body": body_text,
    }


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
