"""
Koach OS v2 — Content Pipeline
=================================
Ideas -> Research -> Outline -> Draft -> Edit -> Publish -> Promote
Inspired by Personal Brain OS content management.
"""

from data_manager import (
    append_jsonl, read_jsonl, generate_id, timestamp_jst, DATA_DIR,
)

CONTENT_FILE = DATA_DIR / "content_ideas.jsonl"

PLATFORMS = ["kindle", "blog", "academic_paper", "sns", "presentation", "newsletter"]

STAGES = ["idea", "research", "outline", "draft", "edit", "publish", "promote"]

STAGE_ICONS = {
    "idea": "💡", "research": "🔍", "outline": "📋", "draft": "✍️",
    "edit": "📝", "publish": "🚀", "promote": "📢",
}


def add_idea(
    title: str,
    description: str,
    platform: str,
    domain: str = "",
    scores: dict | None = None,
) -> dict:
    """Add a new content idea to the pipeline."""
    sc = scores or {
        "alignment": 0, "insight": 0, "audience": 0,
        "timeliness": 0, "effort_impact": 0,
    }
    total = sum(sc.values())

    entry = {
        "id": generate_id("idea"),
        "timestamp": timestamp_jst(),
        "title": title,
        "description": description,
        "platform": platform,
        "domain": domain,
        "stage": "idea",
        "scores": sc,
        "total_score": total,
        "status": "active",
        "notes": [],
    }
    append_jsonl(CONTENT_FILE, entry)
    return entry


def get_ideas(stage: str | None = None, status: str = "active") -> list[dict]:
    """Get content ideas, optionally filtered by stage."""
    items = read_jsonl(CONTENT_FILE, filter_fn=lambda x: x.get("status") == status)
    if stage:
        items = [i for i in items if i.get("stage") == stage]
    return items


def get_pipeline_summary() -> dict:
    """Get count of items per stage."""
    items = get_ideas()
    summary = {s: 0 for s in STAGES}
    for item in items:
        stage = item.get("stage", "idea")
        if stage in summary:
            summary[stage] += 1
    return summary


def advance_stage(idea_id: str, note: str = "") -> dict | None:
    """Move an idea to the next stage. Appends new entry (append-only)."""
    items = read_jsonl(CONTENT_FILE)
    # Find the latest entry for this idea
    target = None
    for item in reversed(items):
        if item.get("id") == idea_id:
            target = item
            break

    if not target:
        return None

    current_stage = target.get("stage", "idea")
    try:
        next_idx = STAGES.index(current_stage) + 1
    except ValueError:
        return None

    if next_idx >= len(STAGES):
        return None  # Already at final stage

    new_entry = {
        **target,
        "id": generate_id("idea"),
        "timestamp": timestamp_jst(),
        "stage": STAGES[next_idx],
        "prev_id": idea_id,
        "notes": target.get("notes", []) + ([note] if note else []),
    }

    # Archive old entry
    archive = {**target, "status": "archived", "archived_at": timestamp_jst()}
    append_jsonl(CONTENT_FILE, archive)
    append_jsonl(CONTENT_FILE, new_entry)
    return new_entry


def get_actionable_ideas(min_score: int = 15) -> list[dict]:
    """Get ideas with total_score >= threshold (ready to execute)."""
    items = get_ideas(stage="idea")
    return [i for i in items if i.get("total_score", 0) >= min_score]


def get_pipeline_context() -> str:
    """Format pipeline summary for system prompt injection."""
    summary = get_pipeline_summary()
    total = sum(summary.values())
    if total == 0:
        return ""

    lines = ["CONTENT PIPELINE STATUS:"]
    for stage, count in summary.items():
        if count > 0:
            icon = STAGE_ICONS.get(stage, "")
            lines.append(f"  {icon} {stage}: {count}")
    return "\n".join(lines)
