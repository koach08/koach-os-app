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


def _build_pdf_native_prompt(today_str: str, source_label: str) -> str:
    return f"""この PDF からカレンダーに追加すべき予定をすべて抽出してください。

今日の日付: {today_str}
ファイル名: {source_label}

PDF には大学関連の日程表（教授会・研究科会議・学科会議・委員会・FD/SD・採点会議・卒論審査・入試業務・年間予定表・時間割など）が含まれている可能性が高い。表組みの日程はすべて1件ずつ別エントリとして抽出してください（10件以上ある場合も省略せず全部出す）。

出力ルール:
- JSON 配列のみ出力。マークダウン・コメント・余計な説明は一切なし
- 各要素: {{"title", "start_iso", "end_iso", "description", "location", "confidence", "event_type", "recurrence", "source_email_id", "source_subject"}}
- start_iso/end_iso: ISO 8601 with +09:00 (例 "2026-06-10T14:00:00+09:00") または終日なら "YYYY-MM-DD"
- event_type: "meeting" | "committee" | "deadline" | "default"
  - 教授会・研究科会議・委員会系 → "committee"
  - 普通の会議・打合せ・授業 → "meeting"
  - 締切・提出期限 → "deadline"
  - その他 → "default"
- recurrence: 週次繰り返し（時間割など）の場合のみ "FREQ=WEEKLY" 形式、それ以外は ""
- source_email_id: "" のまま
- source_subject: ファイル名 "{source_label}" を使う
- 年が書かれていない場合は今日の日付から推測（今が5月で「6月10日」とあれば 2026-06-10）
- 終了時刻が無い場合は開始から1時間後を仮置き

日程表に20件あれば20件、50件あれば50件、すべて返す。1件も漏らさず、しかし作り話は禁止（書かれていない日付は出さない）。"""


def _parse_proposals_json(raw: str, source_label: str) -> tuple[list[dict], str | None]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    if not cleaned.startswith("["):
        first = cleaned.find("[")
        last = cleaned.rfind("]")
        if first != -1 and last != -1 and last > first:
            cleaned = cleaned[first:last + 1]
    parse_error: str | None = None
    try:
        proposals = json.loads(cleaned)
        if not isinstance(proposals, list):
            proposals = []
    except json.JSONDecodeError as e:
        proposals = []
        parse_error = str(e)
    normalized: list[dict] = []
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
            "recurrence": str(p.get("recurrence", "")),
            "source_email_id": "",
            "source_subject": source_label,
        })
    return normalized, parse_error


def _extract_with_ai(full_text: str, source_label: str, engine: str) -> dict:
    """Shared AI extraction for PDF/Excel/text. Returns the same shape as the PDF endpoint."""
    today_str = now_jst().strftime("%Y-%m-%d (%A)")
    system_prompt = f"""You extract calendar events from a document (schedule sheet, syllabus, timetable, meeting agenda).

TODAY IS: {today_str}

The text comes from a PDF/Excel — may contain table-formatted dates, semester schedules, exam schedules, committee schedules, weekly timetables.

Items to extract:
- All meetings, classes, exams, committees, deadlines with dates/times
- 大学関連: 教授会・研究科会議・学科会議・学部会議・研究会・FD・SD・入試業務・採点会議・卒論審査・教務委員会・人事委員会・予算委員会・各種ワーキンググループ etc.
- All-day events if no time specified
- Weekly recurring classes (timetable/時間割): include `recurrence` with the RRULE-compatible info
- Be GENEROUS — include anything resembling a scheduled gathering, even if labeled vaguely (例: ○○について、説明会、報告会、懇談会)

**重要 — 表形式の日程表（教授会日程表・年間予定表など）**:
- 表の行で「6/10(火) 14:00〜16:00 教授会」のような形式を見つけたら、すべて個別のイベントとして抽出
- 月だけの行（例: 「6月」セル → その下に複数の日付）の場合、各日付ごとに別エントリ作成
- 同じ会議が複数月にわたって列挙されている場合（例: 教授会 4/15, 5/13, 6/10, 7/8, …）も全て抽出（必要なら一度に20-50件）
- パイプ区切り `|` で来た行はテーブル行 — 各セルを意味的に解釈（曜日 / 日付 / 時間 / 会議名 / 場所）
- 「定例○○会議」「第N回○○」のような繰り返し型でも、一覧されている全日程を個別エントリにする

Output rules:
- Output ONLY a JSON array. No markdown, no commentary.
- Each item: {{title, start_iso, end_iso, description, location, confidence, event_type, recurrence, source_email_id, source_subject}}
- ISO 8601 with timezone (+09:00) or all-day "YYYY-MM-DD"
- source_email_id: leave ""
- source_subject: use the document filename/sheet name
- event_type: meeting/committee/deadline/default
- title: in Japanese if source is Japanese
- If a year is omitted, assume the most likely year given today's date
- For weekly recurring (e.g. "月曜 1限 線形代数"), set:
    - start_iso to the FIRST occurrence (e.g. semester start week, that Monday)
    - recurrence: "FREQ=WEEKLY;UNTIL=YYYYMMDDT235959Z" (semester end if known, otherwise omit UNTIL)
    - If recurrence not needed (one-off), set recurrence: ""
- For Excel timetable cells, infer the time from period columns (1限=08:45-10:15, 2限=10:30-12:00, 3限=13:00-14:30, 4限=14:45-16:15, 5限=16:30-18:00) unless the document specifies otherwise

Return [] only if no dates can be identified."""

    user_msg = f"Extract calendar events from this document (source: {source_label}):\n\n{full_text[:80000]}"
    selected_engine = engine if engine in DEFAULT_MODELS else "gemini"
    model = DEFAULT_MODELS.get(selected_engine, DEFAULT_MODELS["gemini"])

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
            "recurrence": str(p.get("recurrence", "")),
            "source_email_id": "",
            "source_subject": source_label,
        })

    return {
        "proposals": normalized,
        "engine_used": selected_engine,
        "model_used": model,
        "parse_error": parse_error,
        "ai_raw_preview": response[:500] if not normalized else None,
    }


@router.post("/calendar/extract-events-from-excel")
async def extract_events_from_excel(
    file: UploadFile = File(...),
    engine: str = "gemini",
):
    """Extract calendar candidates from an uploaded Excel (.xlsx) — supports timetables (時間割)."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not available")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="empty file")

    try:
        wb = load_workbook(io.BytesIO(contents), data_only=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel parse failed: {e}")

    sheets_text = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            if any(c.strip() for c in cells):
                rows.append(" | ".join(cells))
        if rows:
            sheets_text.append(f"### Sheet: {sheet_name}\n" + "\n".join(rows))
    full_text = "\n\n".join(sheets_text)

    if not full_text.strip():
        return {
            "proposals": [],
            "parse_error": "Excel から内容を抽出できませんでした",
            "filename": file.filename,
            "sheet_count": len(wb.sheetnames),
        }

    result = _extract_with_ai(full_text, file.filename or "uploaded.xlsx", engine)
    result["filename"] = file.filename
    result["sheet_count"] = len(wb.sheetnames)
    return result


@router.post("/calendar/extract-events-from-pdf")
async def extract_events_from_pdf(
    file: UploadFile = File(...),
    engine: str = "gemini",
):
    """Extract calendar candidates from an uploaded PDF (日程表・年間予定表 etc.)."""
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="empty file")

    # Path A: send the PDF directly to Gemini (multimodal — handles tables/layout/scanned natively)
    try:
        import google.generativeai as genai
        from data_manager import now_jst as _now_jst
        import os as _os
        api_key = _os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            today_str = _now_jst().strftime("%Y-%m-%d (%A)")
            prompt = _build_pdf_native_prompt(today_str, file.filename or "uploaded.pdf")
            model_name = DEFAULT_MODELS.get("gemini", "gemini-2.0-flash-exp")
            mdl = genai.GenerativeModel(model_name=model_name)
            resp = mdl.generate_content(
                [
                    {"mime_type": "application/pdf", "data": contents},
                    prompt,
                ],
                generation_config={"max_output_tokens": 8000, "temperature": 0.2},
            )
            raw = resp.text if hasattr(resp, "text") else str(resp)
            normalized, parse_error = _parse_proposals_json(raw, file.filename or "PDF")
            return {
                "proposals": normalized,
                "filename": file.filename,
                "page_count": 0,  # not extracted in this path
                "engine_used": "gemini-native-pdf",
                "model_used": model_name,
                "parse_error": parse_error,
                "ai_raw_preview": raw[:1500] if not normalized else None,
                "text_preview": "(Gemini が PDF を直接解析しました)",
                "text_length": len(contents),
            }
    except Exception as e:
        # fall through to text extraction path
        gemini_native_error = str(e)
    else:
        gemini_native_error = None

    text_pages: list[str] = []
    # First try pdfplumber (preserves tables/columns), fall back to PyPDF2
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            for page in pdf.pages:
                page_parts: list[str] = []
                # extract tables separately so rows stay aligned
                try:
                    tables = page.extract_tables() or []
                    for table in tables:
                        for row in table:
                            cells = [str(c or "").strip() for c in row]
                            if any(cells):
                                page_parts.append(" | ".join(cells))
                except Exception:
                    pass
                # then plain text (avoid duplicating table content by keeping text last and unique-ish)
                try:
                    txt = page.extract_text() or ""
                    if txt.strip():
                        page_parts.append(txt)
                except Exception:
                    pass
                text_pages.append("\n".join(page_parts))
    except Exception:
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(contents))
            for p in reader.pages:
                try:
                    text_pages.append(p.extract_text() or "")
                except Exception:
                    text_pages.append("")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF parse failed: {e}")

    full_text = "\n\n---PAGE---\n\n".join(text_pages)

    if not full_text.strip():
        return {
            "proposals": [],
            "parse_error": "PDF からテキストを抽出できませんでした（画像のみ・スキャンPDF の可能性）",
            "filename": file.filename,
            "page_count": len(text_pages),
            "text_preview": "",
            "text_length": 0,
        }

    result = _extract_with_ai(full_text, file.filename or "uploaded.pdf", engine)
    result["filename"] = file.filename
    result["page_count"] = len(text_pages)
    result["text_preview"] = full_text[:3000]
    result["text_length"] = len(full_text)
    return result


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
    recurrence: str = ""  # RRULE body, e.g. "FREQ=WEEKLY;UNTIL=20260801T235959Z"


@router.post("/calendar/create-event")
def create_event(req: CreateEventRequest):
    """Create a Google Calendar event with type-aware reminders and optional recurrence."""
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
            recurrence=req.recurrence or None,
        )
        return {
            "id": result.get("id", ""),
            "html_link": result.get("htmlLink", ""),
            "status": result.get("status", ""),
            "event_type_used": result.get("_event_type_used", "default"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calendar event creation failed: {e}")
