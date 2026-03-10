"""
POST/GET /api/analyze — Writing style analysis & style guide generation.
Supports: text input, single/batch file upload, URL fetch, Google Drive shared links.
"""

import io
import re
from urllib.parse import urlparse, parse_qs

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from data_manager import read_style_guide, read_jsonl, VOICE_FILE
from learning_engine import analyze_writing_style, regenerate_style_guide

router = APIRouter()


# ─── Helpers: File Text Extraction ───

def _extract_pdf_text(data: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(p for p in pages if p.strip())
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception:
        pass

    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
        text = "\n\n".join(p for p in pages if p.strip())
        if text.strip():
            return text
    except ImportError:
        pass
    except Exception:
        pass

    raise HTTPException(
        status_code=500,
        detail="PDF text extraction failed. Install: pip install PyPDF2"
    )


def _extract_docx_text(data: bytes) -> str:
    """Extract text from .docx bytes."""
    try:
        import docx
        doc = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except ImportError:
        raise HTTPException(status_code=500, detail="pip install python-docx required")


def _extract_doc_text(data: bytes) -> str:
    """Extract text from legacy .doc via macOS textutil."""
    try:
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            tmp.write(data)
            tmp.flush()
            result = subprocess.run(
                ["textutil", "-convert", "txt", "-stdout", tmp.name],
                capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout
    except Exception:
        pass
    raise HTTPException(status_code=400, detail=".doc: please convert to .docx or .pdf")


def _extract_text_from_bytes(data: bytes, filename: str) -> str:
    """Route file bytes to the appropriate extractor based on extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext in ("txt", "md"):
        return data.decode("utf-8", errors="replace")
    elif ext == "pdf":
        return _extract_pdf_text(data)
    elif ext == "docx":
        return _extract_docx_text(data)
    elif ext == "doc":
        return _extract_doc_text(data)
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported: .{ext}. Use .txt, .md, .pdf, .docx"
        )


# ─── Single Text Analysis ───

class AnalyzeRequest(BaseModel):
    text: str
    context: str = ""
    genre: str = "general"


@router.post("/analyze")
def analyze_text(req: AnalyzeRequest):
    """Analyze a text sample for writing style patterns."""
    if len(req.text.strip()) < 50:
        raise HTTPException(status_code=400, detail="Text too short (minimum 50 characters)")

    result = analyze_writing_style(text=req.text, context=req.context, genre=req.genre)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ─── Single File Upload ───

@router.post("/analyze/upload")
async def analyze_upload(
    file: UploadFile = File(...),
    context: str = Form(""),
    genre: str = Form("general"),
):
    """Upload a single file for writing style analysis."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    data = await file.read()
    content = _extract_text_from_bytes(data, file.filename)

    if len(content.strip()) < 50:
        raise HTTPException(status_code=400, detail="Extracted text too short (minimum 50 characters)")

    result = analyze_writing_style(
        text=content,
        context=context or f"Uploaded: {file.filename}",
        genre=genre,
    )
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return {**result, "extracted_length": len(content)}


# ─── Batch File Upload ───

@router.post("/analyze/batch")
async def analyze_batch(
    files: list[UploadFile] = File(...),
    context: str = Form(""),
    genre: str = Form("general"),
):
    """Upload multiple files at once. Each file is analyzed and saved individually."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    results = []
    errors = []

    for f in files:
        if not f.filename:
            continue
        try:
            data = await f.read()
            content = _extract_text_from_bytes(data, f.filename)

            if len(content.strip()) < 50:
                errors.append({"file": f.filename, "error": "Text too short after extraction"})
                continue

            result = analyze_writing_style(
                text=content,
                context=context or f"Batch upload: {f.filename}",
                genre=genre,
            )

            if "error" in result:
                errors.append({"file": f.filename, "error": result["error"]})
            else:
                results.append({
                    "file": f.filename,
                    "id": result.get("id", ""),
                    "extracted_length": len(content),
                    "voice_summary": result.get("analysis", {}).get("voice_summary", ""),
                })
        except HTTPException as e:
            errors.append({"file": f.filename, "error": e.detail})
        except Exception as e:
            errors.append({"file": f.filename, "error": str(e)})

    return {
        "total": len(files),
        "analyzed": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors,
    }


# ─── Google Drive Shared Link ───

class GDriveRequest(BaseModel):
    url: str
    genre: str = "academic"


def _parse_gdrive_file_id(url: str) -> str | None:
    """Extract file ID from various Google Drive URL formats."""
    parsed = urlparse(url)
    host = parsed.hostname or ""

    if "drive.google.com" not in host and "docs.google.com" not in host:
        return None

    # Format: /file/d/{ID}/...
    match = re.search(r"/(?:file/d|document/d|spreadsheets/d|presentation/d)/([a-zA-Z0-9_-]+)", parsed.path)
    if match:
        return match.group(1)

    # Format: ?id={ID}
    qs = parse_qs(parsed.query)
    if "id" in qs:
        return qs["id"][0]

    # Format: open?id={ID}
    if "/open" in parsed.path and "id" in qs:
        return qs["id"][0]

    return None


def _fetch_gdrive_file(file_id: str) -> tuple[bytes, str]:
    """Download a file from Google Drive via public export. Returns (bytes, guessed_filename)."""
    import requests as req_lib

    session = req_lib.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    })

    # Try direct download (works for publicly shared files)
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    try:
        resp = session.get(download_url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("Content-Type", "")
        data = resp.content

        # If HTML confirmation page for large files, follow the confirm link
        if "text/html" in content_type and len(data) < 50000:
            html = data.decode("utf-8", errors="replace")
            confirm_match = re.search(r'href="(/uc\?export=download[^"]+)"', html)
            if confirm_match:
                confirm_url = "https://drive.google.com" + confirm_match.group(1).replace("&amp;", "&")
                resp2 = session.get(confirm_url, timeout=30, allow_redirects=True)
                resp2.raise_for_status()
                content_type = resp2.headers.get("Content-Type", "")
                data = resp2.content

        # Determine filename from content type
        if "pdf" in content_type:
            filename = f"gdrive_{file_id}.pdf"
        elif "wordprocessingml" in content_type or "msword" in content_type:
            filename = f"gdrive_{file_id}.docx"
        elif "text/plain" in content_type:
            filename = f"gdrive_{file_id}.txt"
        else:
            # Try Google Docs export as plain text first (more reliable), then PDF
            for fmt, ext in [("txt", "txt"), ("pdf", "pdf")]:
                export_url = f"https://docs.google.com/document/d/{file_id}/export?format={fmt}"
                try:
                    resp3 = session.get(export_url, timeout=30, allow_redirects=True)
                    resp3.raise_for_status()
                    data = resp3.content
                    filename = f"gdrive_{file_id}.{ext}"
                    break
                except Exception:
                    continue
            else:
                filename = f"gdrive_{file_id}.pdf"

        return data, filename

    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download from Google Drive: {e}. Make sure the link is set to 'Anyone with the link can view'."
        )


@router.post("/analyze/gdrive")
def analyze_gdrive(req: GDriveRequest):
    """Fetch a file from a Google Drive shared link and analyze it."""
    file_id = _parse_gdrive_file_id(req.url)
    if not file_id:
        raise HTTPException(
            status_code=400,
            detail="Invalid Google Drive URL. Supported formats: drive.google.com/file/d/..., docs.google.com/document/d/..."
        )

    data, filename = _fetch_gdrive_file(file_id)

    if len(data) < 10:
        raise HTTPException(status_code=400, detail="Downloaded file is empty")

    content = _extract_text_from_bytes(data, filename)

    if len(content.strip()) < 50:
        raise HTTPException(status_code=400, detail="Extracted text too short (minimum 50 characters)")

    result = analyze_writing_style(
        text=content,
        context=f"Google Drive: {req.url}",
        genre=req.genre,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return {**result, "source": "gdrive", "extracted_length": len(content), "filename": filename}


# ─── URL Fetch (SNS, web pages) ───

class UrlAnalyzeRequest(BaseModel):
    url: str
    genre: str = "sns"


def _detect_platform(url: str) -> str:
    """Detect SNS platform from URL."""
    host = urlparse(url).hostname or ""
    if "twitter.com" in host or "x.com" in host:
        return "twitter"
    if "instagram.com" in host:
        return "instagram"
    if "facebook.com" in host:
        return "facebook"
    if "note.com" in host:
        return "note"
    if "bsky.app" in host or "bsky.social" in host:
        return "bluesky"
    if "threads.net" in host:
        return "threads"
    if "linkedin.com" in host:
        return "linkedin"
    return "web"


def _fetch_url_text(url: str) -> tuple[str, str]:
    """Fetch text content from a URL. Returns (text, platform)."""
    import requests as req_lib
    from html.parser import HTMLParser

    platform = _detect_platform(url)

    try:
        resp = req_lib.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ja,en;q=0.9",
            },
            timeout=30,
            allow_redirects=True,
        )
        resp.raise_for_status()
        html = resp.text
    except req_lib.exceptions.SSLError as e:
        raise HTTPException(status_code=400, detail=f"SSL error fetching URL. The site may block automated access: {e}")
    except req_lib.exceptions.Timeout:
        raise HTTPException(status_code=400, detail="Request timed out. The site may be slow or blocking access.")
    except req_lib.exceptions.ConnectionError as e:
        raise HTTPException(status_code=400, detail=f"Connection failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.texts: list[str] = []
            self.skip = False
            self.skip_tags = {"script", "style", "nav", "header", "footer", "noscript"}

        def handle_starttag(self, tag, attrs):
            if tag in self.skip_tags:
                self.skip = True

        def handle_endtag(self, tag):
            if tag in self.skip_tags:
                self.skip = False

        def handle_data(self, data):
            if not self.skip:
                stripped = data.strip()
                if stripped:
                    self.texts.append(stripped)

    extractor = TextExtractor()
    extractor.feed(html)
    text = "\n".join(extractor.texts)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text, platform


@router.post("/analyze/url")
def analyze_url(req: UrlAnalyzeRequest):
    """Fetch content from a URL and analyze writing style."""
    parsed = urlparse(req.url)
    if not parsed.scheme or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid URL")

    # Redirect Google Drive links to the gdrive handler
    host = parsed.hostname or ""
    if "drive.google.com" in host or "docs.google.com" in host:
        return analyze_gdrive(GDriveRequest(url=req.url, genre=req.genre))

    text, platform = _fetch_url_text(req.url)

    if len(text.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Could not extract enough text ({len(text.strip())} chars). Page may require auth or JS rendering."
        )

    if len(text) > 10000:
        text = text[:10000]

    result = analyze_writing_style(
        text=text,
        context=f"Fetched from {platform}: {req.url}",
        genre=req.genre,
    )

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return {**result, "platform": platform, "extracted_length": len(text)}


# ─── Style Guide ───

@router.get("/analyze/style-guide")
def get_style_guide():
    """Get the current style guide markdown."""
    content = read_style_guide()
    return {"content": content, "exists": bool(content)}


@router.post("/analyze/regenerate")
def regenerate_guide():
    """Regenerate the style guide from all voice profile entries."""
    content = regenerate_style_guide()
    return {"content": content}


@router.get("/analyze/samples")
def get_sample_count():
    """Get the number of voice profile samples collected."""
    entries = read_jsonl(VOICE_FILE, filter_fn=lambda x: x.get("status") == "active")
    genres = {}
    for e in entries:
        g = e.get("genre", "unknown")
        genres[g] = genres.get(g, 0) + 1
    return {"total": len(entries), "by_genre": genres}
