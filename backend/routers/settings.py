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
    """Get current settings + API key status for all 7 engines."""
    engine_keys = {
        "claude": "ANTHROPIC_API_KEY",
        "gpt": "OPENAI_API_KEY",
        "grok": "XAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "venice": "VENICE_API_KEY",
        "perplexity": "PERPLEXITY_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    has_keys = {engine: bool(get_secret(env_var)) for engine, env_var in engine_keys.items()}

    return {
        "models": DEFAULT_MODELS,
        "available_models": AVAILABLE_MODELS,
        "has_keys": has_keys,
        # Backwards compatibility
        "has_anthropic_key": has_keys["claude"],
        "has_openai_key": has_keys["gpt"],
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
