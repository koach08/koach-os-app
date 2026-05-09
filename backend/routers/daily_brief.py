"""
GET /api/daily-brief — 朝1画面で生活を回すためのDaily Brief
- Gcal 今日の予定
- 直近の決定ログ
- 直近の会話トピック
- L3 介入：「今日3つに絞って」AI問いかけ
"""

from datetime import timedelta
from fastapi import APIRouter, Query

from gcal import is_configured, get_events
from data_manager import (
    read_jsonl,
    LOGS_FILE,
    DECISIONS_FILE,
    FAILURES_FILE,
    TASKS_FILE,
    now_jst,
)
from router import call_ai, DEFAULT_MODELS, AVAILABLE_MODELS

router = APIRouter()


def _format_event(ev: dict) -> dict:
    """Calendar event -> minimal frontend-friendly shape."""
    return {
        "title": ev.get("summary", "(no title)"),
        "start": ev.get("start", ""),
        "end": ev.get("end", ""),
        "all_day": ev.get("all_day", False),
        "location": ev.get("location", ""),
    }


def _recent_decisions(days: int = 3, limit: int = 5) -> list[dict]:
    """直近N日の decisions.jsonl を新しい順で返す。"""
    decisions = read_jsonl(DECISIONS_FILE)
    if not decisions:
        return []
    cutoff = now_jst() - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()
    out = []
    for d in reversed(decisions):
        ts = d.get("timestamp", "")
        if ts < cutoff_iso:
            break
        out.append(
            {
                "title": d.get("title", "")[:80],
                "reasoning": d.get("reasoning", "")[:200],
                "timestamp": ts,
            }
        )
        if len(out) >= limit:
            break
    return out


def _recent_topics(limit: int = 5) -> list[str]:
    """直近の会話トピック。重複排除。"""
    logs = read_jsonl(LOGS_FILE)
    seen: set[str] = set()
    out: list[str] = []
    for log in reversed(logs[-30:]):
        preview = (log.get("user_input_preview") or "").strip()
        if not preview:
            continue
        key = preview[:40]
        if key in seen:
            continue
        seen.add(key)
        out.append(preview[:120])
        if len(out) >= limit:
            break
    return out


def _open_tasks() -> list[dict]:
    """Tasks not done, sorted by due date / priority."""
    state: dict[str, dict] = {}
    for e in read_jsonl(TASKS_FILE):
        tid = e.get("id")
        if not tid:
            continue
        if e.get("_deleted"):
            state.pop(tid, None)
            continue
        state[tid] = e

    open_tasks = [t for t in state.values() if t.get("status") != "done"]
    today = now_jst().strftime("%Y-%m-%d")
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    open_tasks.sort(
        key=lambda t: (
            (t.get("due_date") or "9999-12-31") < today,  # overdue first... wait false sorts first
            t.get("due_date") or "9999-12-31",
            priority_rank.get(t.get("priority", "medium"), 1),
        )
    )
    # Trim fields
    return [
        {
            "id": t["id"],
            "title": t.get("title", ""),
            "status": t.get("status", "todo"),
            "priority": t.get("priority", "medium"),
            "due_date": t.get("due_date"),
            "due_time": t.get("due_time"),
            "category": t.get("category", "personal"),
        }
        for t in open_tasks[:10]
    ]


def _recent_failures(limit: int = 2) -> list[dict]:
    """最近の失敗ログ（学びの再確認用）。"""
    failures = read_jsonl(FAILURES_FILE)
    if not failures:
        return []
    return [
        {
            "what": f.get("what", "")[:80],
            "lesson": f.get("lesson", "")[:200],
        }
        for f in reversed(failures[-limit:])
    ]


@router.get("/daily-brief")
def daily_brief(
    engine: str = Query("claude", description="claude/gpt/grok/gemini/venice/perplexity/groq"),
    model: str | None = Query(None, description="override model id (optional)"),
):
    """
    朝1画面で出すDaily Brief。
    schedule + decisions + topics + failures + AI問いかけ を構造化JSONで返す。
    """
    now = now_jst()

    # 1. Gcal 今日の予定
    if is_configured():
        events_raw = get_events(days_ahead=0)
        schedule = [_format_event(ev) for ev in events_raw]
        gcal_status = "ok"
    else:
        schedule = []
        gcal_status = "not_configured"

    # 2. 直近の決定ログ
    decisions = _recent_decisions(days=3, limit=5)

    # 3. 直近の話題
    topics = _recent_topics(limit=5)

    # 4. 失敗からの学び
    failures = _recent_failures(limit=2)

    # 5. オープンタスク
    tasks = _open_tasks()

    # 5. AI問いかけ（L3介入相当：今日3つに絞れ）
    schedule_text = (
        "\n".join(
            f"- {ev['start'][:16]} {ev['title']}" + (f" @ {ev['location']}" if ev["location"] else "")
            for ev in schedule
        )
        if schedule
        else "(予定なし)"
    )
    decisions_text = (
        "\n".join(f"- {d['title']}" for d in decisions) if decisions else "(直近の決定なし)"
    )
    topics_text = "\n".join(f"- {t}" for t in topics) if topics else "(直近の会話なし)"
    tasks_text = (
        "\n".join(
            f"- [{t['priority']}] {t['title']}"
            + (f" (期限 {t['due_date']})" if t.get("due_date") else "")
            for t in tasks
        )
        if tasks
        else "(オープンなタスクなし)"
    )

    prompt = f"""あなたは Koach OS。志柿のための reflective AI partner。
今は {now.strftime('%Y-%m-%d %H:%M (%A)')} 。
これから1日が始まる。生活を回すための朝のbriefingを出す。

## 今日の予定
{schedule_text}

## 直近3日の決定
{decisions_text}

## 直近の話題
{topics_text}

## オープンタスク
{tasks_text}

## 出力ルール
- 「今日やる3つ」を提案する。多すぎ判定したら「絞れ」と言う
- 予定の隙間時間をどう使うか提案
- 直近の決定を1つだけリマインド（忘れがちなものを優先）
- L3 介入レベル: 戦略的視点で1つ問いを立てる（「本当に必要？」など）
- 200字以内。箇条書き4-5項目
- 日本語、です/ます調、煽らない、抽象名詞「〜性」は使わない"""

    # Resolve model: explicit > engine default > claude default
    if engine not in DEFAULT_MODELS:
        engine = "claude"
    resolved_model = model or DEFAULT_MODELS.get(engine, DEFAULT_MODELS["claude"])

    try:
        ai_brief = call_ai(
            messages=[{"role": "user", "content": "今日のbriefingをお願いします。"}],
            system=prompt,
            engine=engine,
            model=resolved_model,
            max_tokens=600,
        )
    except Exception as e:
        ai_brief = f"(AI brief 失敗: {e})"

    return {
        "generated_at": now.isoformat(),
        "schedule": schedule,
        "gcal_status": gcal_status,
        "decisions": decisions,
        "topics": topics,
        "failures": failures,
        "tasks": tasks,
        "ai_brief": ai_brief,
        "engine_used": engine,
        "model_used": resolved_model,
    }
