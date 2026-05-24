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
    """Load token from env var (base64 first, then JSON), then local file.

    Priority:
      1. GOOGLE_TOKEN_JSON_B64 (slot 1) / GOOGLE_TOKEN_JSON_N_B64 (slot N) — base64
      2. GOOGLE_TOKEN_JSON / GOOGLE_TOKEN_JSON_N — plain JSON
      3. token.json / token_N.json file (local dev)
    """
    import base64

    # 1. Try base64-encoded env var (avoids dashboard newline issues)
    b64_name = _token_env_name(slot) + "_B64"
    b64_str = get_secret(b64_name)
    if b64_str:
        try:
            decoded = base64.b64decode(b64_str.strip()).decode("utf-8")
            return json.loads(decoded)
        except Exception:
            pass

    # 2. Try plain JSON env var
    token_str = get_secret(_token_env_name(slot))
    if token_str:
        cleaned = token_str.strip().replace("\r", "").replace("\n", "")
        try:
            return json.loads(cleaned)
        except Exception:
            try:
                return json.loads(token_str)
            except Exception:
                pass

    # 3. Local file fallback
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

    全 slot × 全 visible calendar を横断する。
    Returns list of {summary, start, end, location, description}.
    """
    if not is_configured():
        return []

    now = now_jst()
    target = now + timedelta(days=days_ahead)
    start_of_day = target.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = target.replace(hour=23, minute=59, second=59, microsecond=0)

    # 全 slot × 全 visible calendar から拾い、日付範囲でフィルタ
    rows = list_events_range_multi(
        start_of_day.strftime("%Y-%m-%d"),
        (end_of_day + timedelta(days=1)).strftime("%Y-%m-%d"),
    )
    day_str = start_of_day.strftime("%Y-%m-%d")
    events: list[dict] = []
    for r in rows:
        s = r.get("start_iso") or ""
        e_ = r.get("end_iso") or s
        if not s:
            continue
        # その日に被るもの (all-day 含む)
        if not (s[:10] <= day_str <= (e_[:10] or s[:10])):
            continue
        events.append({
            "id": r.get("id", ""),
            "summary": r.get("title", "(no title)"),
            "start": s,
            "end": e_,
            "location": r.get("location", ""),
            "description": r.get("description", ""),
            "all_day": r.get("all_day", False),
        })
    events.sort(key=lambda x: x.get("start", ""))
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
    recurrence: str | None = None,
) -> dict:
    """Create a calendar event with type-aware reminders and optional weekly recurrence.

    event_type: meeting / committee / deadline / default / None (auto-detect).
    recurrence: RRULE body without the "RRULE:" prefix (e.g. "FREQ=WEEKLY;UNTIL=20260801T235959Z").
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

    if recurrence:
        rrule = recurrence.strip()
        if not rrule.upper().startswith("RRULE:"):
            rrule = "RRULE:" + rrule
        body["recurrence"] = [rrule]

    result = service.events().insert(calendarId="primary", body=body).execute()
    result["_event_type_used"] = resolved_type
    return result


def _all_visible_calendar_ids() -> list[str]:
    """slot 1 の visible calendar 群（後方互換）."""
    return [cid for (_s, cid) in _all_visible_calendar_sources()]


def _all_visible_calendar_sources() -> list[tuple[int, str]]:
    """全 slot を横断して (slot, calendar_id) を返す。

    各 slot の primary + その slot で見えている隠してないカレンダーを返す。
    EXTRA_CALENDAR_IDS が指定されていれば slot 1 にのみ追加。
    """
    import os
    out: list[tuple[int, str]] = []
    seen: set[str] = set()
    explicit = [c.strip() for c in os.environ.get("EXTRA_CALENDAR_IDS", "").split(",") if c.strip()]
    for slot in _configured_slots():
        try:
            service = _get_service(slot)
            cal_list = service.calendarList().list(showHidden=False, showDeleted=False).execute()
        except Exception:
            # primary だけは入れておく
            key = f"{slot}:primary"
            if key not in seen:
                seen.add(key)
                out.append((slot, "primary"))
            continue
        items = cal_list.get("items", []) or []
        has_primary = False
        for c in items:
            if c.get("hidden") or c.get("deleted"):
                continue
            if c.get("selected") is False:
                continue
            cid = c.get("id", "")
            if not cid:
                continue
            if c.get("primary"):
                has_primary = True
            key = f"{slot}:{cid}"
            if key in seen:
                continue
            seen.add(key)
            out.append((slot, cid))
        if not has_primary:
            key = f"{slot}:primary"
            if key not in seen:
                seen.add(key)
                out.append((slot, "primary"))
    # slot 1 の EXTRA_CALENDAR_IDS を追加
    for cid in explicit:
        key = f"1:{cid}"
        if key not in seen:
            seen.add(key)
            out.append((1, cid))
    return out


def list_events_range(start_date: str, end_date: str) -> list[dict]:
    """List events in a date range (YYYY-MM-DD strings, end exclusive).

    全 slot × 全 visible calendar を横断 (japanesebusinessman4 + kshgks59 等)。
    """
    return list_events_range_multi(start_date, end_date)


def delete_event(event_id: str) -> None:
    service = _get_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()


def _extra_calendar_ids() -> list[str]:
    """EXTRA_CALENDAR_IDS env (comma-separated) — 妻 / 子供 / 共有 calendar の ID."""
    import os
    raw = os.environ.get("EXTRA_CALENDAR_IDS", "")
    return [c.strip() for c in raw.split(",") if c.strip()]


def list_events_range_multi(start_date: str, end_date: str, calendar_ids: list[str] | None = None) -> list[dict]:
    """全 slot × 指定 calendar 群から events を集めて1リストにする。

    calendar_ids=None なら _all_visible_calendar_sources() で全 slot 自動列挙。
    後方互換のため calendar_ids リストを渡された場合は slot 1 のみで処理する。
    """
    from datetime import datetime, timezone, timedelta
    tz = timezone(timedelta(hours=9))
    start_dt = datetime.fromisoformat(start_date).replace(tzinfo=tz)
    end_dt = datetime.fromisoformat(end_date).replace(tzinfo=tz)

    if calendar_ids is not None:
        sources: list[tuple[int, str]] = [(1, cid) for cid in calendar_ids]
    else:
        sources = _all_visible_calendar_sources()

    seen: set[str] = set()
    out: list[dict] = []
    service_cache: dict[int, object] = {}

    for slot, cid in sources:
        if slot not in service_cache:
            try:
                service_cache[slot] = _get_service(slot)
            except Exception:
                service_cache[slot] = None
        service = service_cache[slot]
        if service is None:
            continue
        try:
            events_result = service.events().list(
                calendarId=cid,
                timeMin=start_dt.astimezone(timezone.utc).isoformat(),
                timeMax=end_dt.astimezone(timezone.utc).isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=500,
            ).execute()
        except Exception:
            continue
        for ev in events_result.get("items", []):
            evid = ev.get("id", "")
            key = f"{slot}:{cid}:{evid}"
            if key in seen:
                continue
            seen.add(key)
            start = ev.get("start", {})
            end_ = ev.get("end", {})
            out.append({
                "id": evid,
                "calendar_id": cid,
                "slot": slot,
                "title": ev.get("summary", "(無題)"),
                "start_iso": start.get("dateTime") or start.get("date") or "",
                "end_iso": end_.get("dateTime") or end_.get("date") or "",
                "all_day": "date" in start,
                "location": ev.get("location", ""),
                "description": ev.get("description", ""),
                "html_link": ev.get("htmlLink", ""),
                "event_type": detect_event_type(ev.get("summary", ""), ev.get("description", "")),
            })
    out.sort(key=lambda e: e["start_iso"])
    return out


def list_family_events_range(start_date: str, end_date: str) -> list[dict]:
    """EXTRA_CALENDAR_IDS で指定された家族 calendar の events のみ。"""
    extras = _extra_calendar_ids()
    if not extras:
        return []
    return list_events_range_multi(start_date, end_date, calendar_ids=extras)


def list_upcoming_events(days_ahead: int = 7) -> list[dict]:
    """Read upcoming events from all visible calendars (primary + subscribed)."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days_ahead)
    start_date = now.strftime("%Y-%m-%d")
    end_date = end.strftime("%Y-%m-%d")
    cal_ids = _all_visible_calendar_ids()
    events = list_events_range_multi(start_date, end_date, calendar_ids=cal_ids)
    # 過去のものはフィルタ (timeMin 厳密適用)
    now_iso = now.isoformat()
    return [e for e in events if (e.get("end_iso") or e.get("start_iso") or "") >= now_iso[:19]]


def list_recent_emails(days: int = 3, max_results: int = 20, slot: int = 1) -> list[dict]:
    """Fetch recent emails from a single slot. Uses Gmail batch API for speed."""
    service = _get_gmail_service(slot)
    query = f"newer_than:{days}d -in:spam -in:trash"

    listing = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    msg_refs = listing.get("messages", [])
    if not msg_refs:
        return []

    # Batch API: send multiple messages.get in a single HTTP request. Max 100 per batch.
    BATCH_LIMIT = 50  # keep batches small for reliability
    results: dict[str, dict] = {}

    def callback(request_id, response, exception):
        if exception is None and response is not None:
            results[request_id] = response

    emails: list[dict] = []
    for chunk_start in range(0, len(msg_refs), BATCH_LIMIT):
        chunk = msg_refs[chunk_start:chunk_start + BATCH_LIMIT]
        batch = service.new_batch_http_request(callback=callback)
        for i, ref in enumerate(chunk):
            batch.add(
                service.users().messages().get(userId="me", id=ref["id"], format="full"),
                request_id=f"{chunk_start}_{i}",
            )
        try:
            batch.execute()
        except Exception:
            continue

    for rid, msg in results.items():
        try:
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
