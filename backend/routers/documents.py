"""
POST /api/documents/extract-tasks — upload a document, extract tasks via AI.
"""

import io
import json
import re
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from data_manager import append_jsonl, TASKS_FILE, generate_id, timestamp_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()


# ─── Text extraction (mirrors analyze.py) ──────────────


def _extract_pdf_text(data: bytes) -> str:
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {e}")


def _extract_text(data: bytes, filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if ext in ("txt", "md", "csv"):
        return data.decode("utf-8", errors="replace")
    if ext == "pdf":
        return _extract_pdf_text(data)
    if ext == "docx":
        try:
            import zipfile
            from xml.etree import ElementTree as ET
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                with zf.open("word/document.xml") as f:
                    tree = ET.parse(f)
                    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                    paragraphs = []
                    for p in tree.iter(f"{ns}p"):
                        text = "".join(t.text or "" for t in p.iter(f"{ns}t"))
                        paragraphs.append(text)
                    return "\n".join(paragraphs)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DOCX extraction failed: {e}")
    raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext} (use .txt, .md, .pdf, .docx)")


# ─── Models ─────────────────────────────────────────────


class TaskProposal(BaseModel):
    title: str
    description: str = ""
    priority: str = "medium"
    due_date: str | None = None
    estimated_minutes: int | None = None
    category: str = "personal"


class CreateFromProposalsRequest(BaseModel):
    proposals: list[TaskProposal]


# ─── Endpoints ──────────────────────────────────────────


@router.post("/documents/extract-tasks")
async def extract_tasks_from_document(
    file: UploadFile = File(...),
    engine: str = Form("gemini"),
):
    """Upload a document, extract task candidates via AI."""
    data = await file.read()
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 10MB)")

    text = _extract_text(data, file.filename or "document")
    if not text.strip():
        return {"proposals": [], "extracted_chars": 0}

    # Cap to keep prompts reasonable; Gemini handles long context but cost matters
    text_capped = text[:30000]

    system_prompt = """You extract actionable tasks from documents (research papers, syllabi, meeting notes, project plans, etc.).

Rules:
- Output ONLY a JSON array. No markdown, no commentary.
- Each item: {title, description, priority, due_date, estimated_minutes, category}
- title: imperative-mood, concise, in document's language (Japanese stays Japanese)
- description: brief context (1 sentence max)
- priority: "high" / "medium" / "low" — judge by urgency/importance signals in text
- due_date: "YYYY-MM-DD" if explicit deadline mentioned, else null
- estimated_minutes: rough estimate (15/30/60/120/240/480), null if unclear
- category: one of "research" / "teaching" / "platform" / "revenue" / "personal" / "business"
- Skip vague aspirations; only extract concrete deliverables/actions
- Skip already-completed items
- 5-15 items typical; return [] if nothing actionable

Return [] if document is purely informational (e.g., article, news)."""

    user_msg = f"Extract tasks from this document:\n\n{text_capped}"

    if engine not in DEFAULT_MODELS:
        engine = "gemini"
    model = DEFAULT_MODELS[engine]

    try:
        response = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
            engine=engine,
            model=model,
            max_tokens=2500,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI task extraction failed: {e}")

    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        proposals = json.loads(cleaned)
        if not isinstance(proposals, list):
            proposals = []
    except json.JSONDecodeError:
        proposals = []

    valid_priority = {"high", "medium", "low"}
    valid_category = {"research", "teaching", "platform", "revenue", "personal", "business"}

    normalized = []
    for p in proposals:
        if not isinstance(p, dict):
            continue
        normalized.append({
            "title": str(p.get("title", ""))[:200],
            "description": str(p.get("description", ""))[:500],
            "priority": p.get("priority", "medium") if p.get("priority") in valid_priority else "medium",
            "due_date": p.get("due_date") if isinstance(p.get("due_date"), str) else None,
            "estimated_minutes": p.get("estimated_minutes") if isinstance(p.get("estimated_minutes"), int) else None,
            "category": p.get("category", "personal") if p.get("category") in valid_category else "personal",
        })

    return {
        "proposals": normalized,
        "extracted_chars": len(text),
        "filename": file.filename,
        "engine_used": engine,
        "model_used": model,
    }


@router.post("/documents/create-tasks-batch")
def create_tasks_batch(req: CreateFromProposalsRequest):
    """Create multiple tasks at once from accepted proposals."""
    created = []
    now = timestamp_jst()
    for p in req.proposals:
        task = {
            "id": generate_id("task"),
            "title": p.title,
            "description": p.description,
            "status": "todo",
            "priority": p.priority,
            "due_date": p.due_date,
            "due_time": None,
            "estimated_minutes": p.estimated_minutes,
            "category": p.category,
            "gcal_event_id": None,
            "created_at": now,
            "updated_at": now,
            "completed_at": None,
        }
        append_jsonl(TASKS_FILE, task)
        created.append(task)
    return {"created": created, "count": len(created)}
