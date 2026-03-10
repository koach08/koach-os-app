"""
GET/POST /api/review — Weekly review generation & stats.
"""

from collections import Counter
from fastapi import APIRouter
from data_manager import (
    read_jsonl, append_jsonl, get_logs_since,
    WEEKLY_FILE, LOGS_FILE, generate_id, timestamp_jst, now_jst,
)
from datetime import timedelta

router = APIRouter()


@router.get("/review/stats")
def get_stats(days: int = 7):
    """Get interaction statistics for the period."""
    logs = get_logs_since(days)

    domains = Counter(l.get("domain", "unknown") for l in logs)
    levels = Counter(l.get("intervention_level", "L1") for l in logs)
    engines = Counter(l.get("routing", {}).get("engine", "unknown") for l in logs)

    bias_counts = Counter()
    for l in logs:
        for b in l.get("cognitive_biases", {}).get("detected", []):
            bias_counts[b] += 1

    counterpoints = sum(1 for l in logs if l.get("intervention_level", "L1") in ("L2", "L3", "L4"))
    counterpoint_rate = (counterpoints / len(logs) * 100) if logs else 0

    return {
        "total_interactions": len(logs),
        "domain_distribution": dict(domains),
        "level_distribution": dict(levels),
        "engine_distribution": dict(engines),
        "bias_frequency": dict(bias_counts),
        "counterpoint_rate_pct": round(counterpoint_rate, 1),
        "period_days": days,
    }


@router.post("/review/generate")
def generate_weekly_review():
    """Generate and store a weekly summary."""
    now = now_jst()
    period_start = (now - timedelta(days=7)).isoformat()
    period_end = now.isoformat()
    logs = get_logs_since(7)

    domains = Counter(l.get("domain", "unknown") for l in logs)
    levels = Counter(l.get("intervention_level", "L1") for l in logs)
    engines = Counter(l.get("routing", {}).get("engine", "unknown") for l in logs)

    bias_counts = Counter()
    for l in logs:
        for b in l.get("cognitive_biases", {}).get("detected", []):
            bias_counts[b] += 1

    counterpoints = sum(1 for l in logs if l.get("intervention_level", "L1") in ("L2", "L3", "L4"))
    counterpoint_rate = (counterpoints / len(logs) * 100) if logs else 0

    summary = {
        "id": generate_id("weekly"),
        "period_start": period_start,
        "period_end": period_end,
        "total_interactions": len(logs),
        "domain_distribution": dict(domains),
        "level_distribution": {"L1": levels.get("L1", 0), "L2": levels.get("L2", 0), "L3": levels.get("L3", 0), "L4": levels.get("L4", 0)},
        "bias_frequency": dict(bias_counts),
        "counterpoint_rate_pct": round(counterpoint_rate, 1),
        "counterpoint_acceptance_rate_pct": 0,
        "routing_distribution": {"claude": engines.get("claude", 0), "gpt": engines.get("gpt", 0)},
        "generated_at": timestamp_jst(),
    }

    append_jsonl(WEEKLY_FILE, summary)
    return summary


@router.get("/review/history")
def get_review_history():
    """Get all past weekly summaries."""
    summaries = read_jsonl(WEEKLY_FILE)
    return {"summaries": summaries}
