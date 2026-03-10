"""
GET/PUT /api/settings — Settings management.
"""

import io
import subprocess
import zipfile
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from data_manager import (
    get_secret, DATA_DIR, MEMORY_DIR,
    export_jsonl, LOGS_FILE, WEEKLY_FILE, DECISIONS_FILE,
    FAILURES_FILE, FEEDBACK_FILE, VOICE_FILE,
)
from router import DEFAULT_MODELS, AVAILABLE_MODELS

router = APIRouter()


@router.get("/settings")
def get_settings():
    """Get current settings."""
    return {
        "models": DEFAULT_MODELS,
        "available_models": AVAILABLE_MODELS,
        "has_anthropic_key": bool(get_secret("ANTHROPIC_API_KEY")),
        "has_openai_key": bool(get_secret("OPENAI_API_KEY")),
    }


@router.get("/settings/export")
def export_all_data():
    """Export all data as ZIP."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filepath in [LOGS_FILE, WEEKLY_FILE, DECISIONS_FILE, FAILURES_FILE, FEEDBACK_FILE, VOICE_FILE]:
            if filepath.exists():
                zf.writestr(f"data/{filepath.name}", filepath.read_text(encoding="utf-8"))

        # Memory files
        for f in MEMORY_DIR.iterdir():
            if f.is_file():
                zf.writestr(f"memory/{f.name}", f.read_text(encoding="utf-8"))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=koach_os_export.zip"},
    )


@router.post("/settings/open-claude-code")
def open_claude_code():
    """Open Claude Code in Terminal at the project directory."""
    project_dir = Path(__file__).parent.parent.parent
    subprocess.Popen(
        ["open", "-a", "Terminal", str(project_dir)],
        cwd=str(project_dir),
    )
    return {"status": "ok", "message": "Terminal opened at project directory. Run 'claude' to start Claude Code."}
