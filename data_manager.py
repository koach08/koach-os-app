"""
Koach OS v2 — Data Manager
============================
Append-only JSONL + YAML utilities for research data.
All timestamps in JST (+09:00).
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Callable

import yaml

# ─── Paths ───
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MEMORY_DIR = BASE_DIR / "memory"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
MEMORY_DIR.mkdir(exist_ok=True)
KNOWLEDGE_DIR.mkdir(exist_ok=True)

# Data files
LOGS_FILE = DATA_DIR / "interaction_logs.jsonl"
WEEKLY_FILE = DATA_DIR / "weekly_summaries.jsonl"
DECISIONS_FILE = DATA_DIR / "decisions.jsonl"
FEEDBACK_FILE = DATA_DIR / "feedback_patterns.jsonl"
VOICE_FILE = DATA_DIR / "voice_profile.jsonl"
FAILURES_FILE = DATA_DIR / "failures.jsonl"
TASKS_FILE = DATA_DIR / "tasks.jsonl"
MEMOS_FILE = DATA_DIR / "memos.jsonl"
TRAINING_PROGRESS_FILE = DATA_DIR / "training_progress.jsonl"

# Memory files
HEURISTICS_FILE = MEMORY_DIR / "heuristics.yaml"
EXPERIENCES_FILE = MEMORY_DIR / "experiences.jsonl"
STYLE_GUIDE_FILE = MEMORY_DIR / "style_guide.md"

# JST timezone
JST = timezone(timedelta(hours=9))


def now_jst() -> datetime:
    """Return current datetime in JST."""
    return datetime.now(JST)


def timestamp_jst() -> str:
    """Return current ISO 8601 timestamp with +09:00."""
    return now_jst().isoformat()


def generate_id(prefix: str) -> str:
    """Generate a timestamped ID like 'log_20260226_143022'."""
    return f"{prefix}_{now_jst().strftime('%Y%m%d_%H%M%S')}"


# ─── JSONL Operations ───

def append_jsonl(filepath: Path, entry: dict) -> None:
    """Append a single JSON entry to a JSONL file. NEVER overwrite."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")


def read_jsonl(filepath: Path, filter_fn: Callable | None = None) -> list[dict]:
    """Read all entries from JSONL, optionally filtered. Skip schema lines."""
    if not filepath.exists():
        return []
    entries = []
    for line in filepath.read_text(encoding="utf-8").strip().split("\n"):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
            if obj.get("_schema"):
                continue
            if filter_fn and not filter_fn(obj):
                continue
            entries.append(obj)
        except json.JSONDecodeError:
            continue
    return entries


def init_jsonl(filepath: Path, schema_name: str, description: str) -> None:
    """Create JSONL file with schema header if it doesn't exist."""
    if not filepath.exists():
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps({
                "_schema": schema_name,
                "_version": "2.0",
                "_description": description,
            }, ensure_ascii=False) + "\n")


def export_jsonl(filepath: Path) -> str:
    """Return full JSONL content as string for download."""
    if not filepath.exists():
        return ""
    return filepath.read_text(encoding="utf-8")


def get_recent_logs(n: int = 50) -> list[dict]:
    """Get last N interaction logs."""
    logs = read_jsonl(LOGS_FILE)
    return logs[-n:]


def get_logs_since(days: int = 7) -> list[dict]:
    """Get logs from last N days."""
    cutoff = (now_jst() - timedelta(days=days)).isoformat()
    return read_jsonl(LOGS_FILE, filter_fn=lambda x: x.get("timestamp", "") >= cutoff)


# ─── YAML Operations ───

def read_yaml(filepath: Path) -> dict:
    """Read YAML file. Returns empty dict if not found."""
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def update_yaml(filepath: Path, data: dict) -> None:
    """Write YAML file (YAML files are mutable, unlike JSONL)."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


# ─── Style Guide Operations ───

def write_style_guide(content: str) -> None:
    """Write style guide markdown to memory/style_guide.md (mutable file)."""
    STYLE_GUIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STYLE_GUIDE_FILE.write_text(content, encoding="utf-8")


def read_style_guide() -> str:
    """Read style guide markdown. Returns empty string if not found."""
    if not STYLE_GUIDE_FILE.exists():
        return ""
    return STYLE_GUIDE_FILE.read_text(encoding="utf-8")


# ─── Secrets ───

def get_secret(key: str, default: str | None = None) -> str | None:
    """Get secret from Streamlit secrets, env vars, or .env file."""
    # 1. Streamlit secrets
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        pass
    # 2. Environment variable
    val = os.environ.get(key)
    if val:
        return val
    # 3. .env file
    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


# ─── API Cost Tracking ───

COSTS_FILE = DATA_DIR / "api_costs.jsonl"

# Pricing per million tokens (input_usd, output_usd)
API_PRICING = {
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "gpt-5.4": (2.50, 15.0),
    "gpt-5.2": (1.75, 14.0),
    "gpt-5.1": (1.25, 10.0),
    "gpt-5": (1.25, 10.0),
    "gpt-4.1": (2.0, 8.0),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "text-embedding-3-small": (0.02, 0.0),
}


def log_api_cost(model: str, input_tokens: int, output_tokens: int, feature: str = "chat") -> dict:
    """Log API cost for an interaction. Returns the cost entry."""
    pricing = API_PRICING.get(model, (0.0, 0.0))
    input_cost = input_tokens / 1_000_000 * pricing[0]
    output_cost = output_tokens / 1_000_000 * pricing[1]
    total_cost = input_cost + output_cost

    entry = {
        "id": generate_id("cost"),
        "timestamp": timestamp_jst(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total_cost, 6),
        "feature": feature,
    }
    append_jsonl(COSTS_FILE, entry)
    return entry


def get_costs_since(days: int = 30) -> list[dict]:
    """Get API cost entries from last N days."""
    cutoff = (now_jst() - timedelta(days=days)).isoformat()
    return read_jsonl(COSTS_FILE, filter_fn=lambda x: x.get("timestamp", "") >= cutoff)


def get_total_cost(days: int = 30) -> float:
    """Get total API cost in USD for last N days."""
    costs = get_costs_since(days)
    return sum(c.get("total_cost_usd", 0) for c in costs)


# ─── Initialize all data files ───

def init_all_data_files() -> None:
    """Initialize all JSONL data files with schema headers."""
    init_jsonl(LOGS_FILE, "interaction_log", "Koach OS v2 interaction logs — research data")
    init_jsonl(WEEKLY_FILE, "weekly_summary", "Weekly review summaries")
    init_jsonl(DECISIONS_FILE, "decision", "Key decisions with reasoning")
    init_jsonl(FEEDBACK_FILE, "feedback_pattern", "Feedback acceptance patterns")
    init_jsonl(VOICE_FILE, "voice_profile", "Writing style observations")
    init_jsonl(FAILURES_FILE, "failure", "Failures and lessons learned")
    init_jsonl(EXPERIENCES_FILE, "experience", "Key experiences with emotional weight")
    init_jsonl(COSTS_FILE, "api_cost", "API usage costs for ROI tracking")

    # Init heuristics.yaml if not exists
    if not HEURISTICS_FILE.exists():
        update_yaml(HEURISTICS_FILE, {
            "rules_of_thumb": [
                {"rule": "Family > Students > Research > Platform > Revenue > Personal growth",
                 "source": "core_values", "confidence": 1.0},
                {"rule": "Morning sessions have higher acceptance rate for critical feedback",
                 "source": "initial_hypothesis", "confidence": 0.5},
            ],
            "last_updated": timestamp_jst(),
        })
