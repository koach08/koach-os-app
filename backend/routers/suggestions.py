"""
GET /api/suggestions — Dynamic welcome prompts based on recent activity.
"""

from fastapi import APIRouter
from data_manager import read_jsonl, LOGS_FILE, DECISIONS_FILE, FAILURES_FILE

router = APIRouter()


@router.get("/suggestions")
def get_suggestions():
    """Generate context-aware prompt suggestions from recent activity."""
    # Get recent logs
    logs = read_jsonl(LOGS_FILE)
    decisions = read_jsonl(DECISIONS_FILE)
    failures = read_jsonl(FAILURES_FILE)

    suggestions = []

    # From recent interactions — extract domains and topics
    recent_logs = logs[-20:] if logs else []
    recent_domains = set()
    recent_topics = []
    for log in reversed(recent_logs):
        domain = log.get("domain", "")
        preview = log.get("user_input_preview", "")
        if domain:
            recent_domains.add(domain)
        if preview and len(recent_topics) < 3:
            # Create a follow-up suggestion
            short = preview[:60] + ("..." if len(preview) > 60 else "")
            recent_topics.append(short)

    # Domain-based suggestions
    domain_prompts = {
        "research": "研究の進捗を振り返ろう",
        "teaching": "今週の授業準備で優先すべきことは？",
        "platform": "プラットフォーム開発の次のステップは？",
        "revenue": "収益化の戦略を見直そう",
        "personal": "最近の自分の判断パターンを振り返ろう",
        "business": "ビジネス面で今一番重要なことは？",
    }

    for domain in recent_domains:
        if domain in domain_prompts and len(suggestions) < 4:
            suggestions.append(domain_prompts[domain])

    # From recent decisions — check for unresolved ones
    recent_decisions = decisions[-5:] if decisions else []
    for dec in reversed(recent_decisions):
        title = dec.get("title", "")
        if title and len(suggestions) < 4:
            suggestions.append(f"「{title[:30]}」の判断を振り返る")
            break

    # From failures — suggest learning
    if failures:
        latest_fail = failures[-1]
        lesson = latest_fail.get("lesson", "")
        if lesson and len(suggestions) < 4:
            suggestions.append("最近の失敗から学んだことを活かせているか？")

    # Fill with defaults if not enough
    defaults = [
        "今週何を優先すべき？",
        "最近の判断を振り返ろう",
        "考えを整理したい",
        "新しいアイデアを議論しよう",
    ]
    for d in defaults:
        if len(suggestions) >= 4:
            break
        if d not in suggestions:
            suggestions.append(d)

    return {"suggestions": suggestions[:4]}
