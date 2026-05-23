"""
GET /api/weekly-review — 週次レビュー自動生成。
過去7日の完了ログ + decisions + private chat 件数 + Calendar 実績 + focus sessions を
AI に集約させて、週報 + 翌週バックログ繰越提案を返す。
"""

from __future__ import annotations

from datetime import timedelta
from fastapi import APIRouter, Query

from data_manager import (
    now_jst,
    read_jsonl,
    DECISIONS_FILE,
    FAILURES_FILE,
    TASKS_FILE,
)
from router import call_ai, DEFAULT_MODELS

router = APIRouter()


@router.get("/weekly-review")
def weekly_review(engine: str = Query("claude")):
    now = now_jst()
    cutoff = (now.date() - timedelta(days=6)).isoformat()
    cutoff_iso = (now - timedelta(days=7)).isoformat()

    # 完了
    try:
        from routers.completions import _current_state
        state = _current_state()
        completions = [v for (_k, _r, d), v in state.items() if d >= cutoff]
        completions.sort(key=lambda x: x.get("date", ""))
    except Exception:
        completions = []

    # focus
    try:
        from routers.focus_timer import focus_week
        focus = focus_week()
    except Exception:
        focus = {"by_day": {}, "by_category_total": {}, "session_count": 0}

    # decisions
    decisions = [d for d in read_jsonl(DECISIONS_FILE) if d.get("timestamp", "") >= cutoff_iso]
    failures = [f for f in read_jsonl(FAILURES_FILE) if f.get("timestamp", "") >= cutoff_iso]

    # tasks (open) — 来週への繰越候補
    state_tasks: dict[str, dict] = {}
    for e in read_jsonl(TASKS_FILE):
        tid = e.get("id")
        if not tid:
            continue
        if e.get("_deleted"):
            state_tasks.pop(tid, None)
            continue
        state_tasks[tid] = e
    open_tasks = [t for t in state_tasks.values() if t.get("status") != "done"][:15]

    # Coach バックログ
    try:
        from routers.productivity import _load_backlog
        backlog_open = [b for b in _load_backlog() if not b.get("done")]
    except Exception:
        backlog_open = []

    by_cat = focus.get("by_category_total", {})
    cat_text = "\n".join(f"  - {k}: {v} 分" for k, v in sorted(by_cat.items(), key=lambda x: -x[1])) or "  (集中タイマー記録なし)"

    completion_text = "\n".join(f"- {c.get('date','')[5:]} {c.get('title','')}" for c in completions[-20:]) or "(完了ログなし)"
    decision_text = "\n".join(f"- {d.get('title','')}" for d in decisions[-8:]) or "(決定なし)"
    failure_text = "\n".join(f"- {f.get('what','')} → {f.get('lesson','')}" for f in failures[-5:]) or "(失敗ログなし)"
    backlog_text = "\n".join(f"- [{b.get('urgency','m')}] {b.get('title','')}" for b in backlog_open[:15]) or "(バックログなし)"

    prompt = f"""あなたは Koach OS。一週間の振り返りを担当する。
今は {now.strftime('%Y-%m-%d (%A)')}。

## 完了ログ ({len(completions)}件)
{completion_text}

## 集中タイマーのカテゴリ別配分
{cat_text}
合計 {focus.get('session_count', 0)} セッション

## 直近の決定
{decision_text}

## 失敗から
{failure_text}

## 未完バックログ
{backlog_text}

## 出力ルール
出力フォーマット:

### 今週の動き (3行)
- 何が進んだか、何が止まったか、何が想定外だったか

### カテゴリ別配分の所見 (2-3行)
- 偏り、家族・健康・休息への配分が足りているか、削るべき領域

### 来週への繰越し (最大5件)
- バックログから「来週やる」だけ抜く。後回しでよいものは捨てる提案も書く

### 来週の1つの問い (L3 介入)
- 戦略的視点で本人に投げる問い 1つだけ

トーン: 簡潔、です/ます調、煽らない、抽象名詞「〜性」NG、一人称「自分」。
800字以内。"""

    if engine not in DEFAULT_MODELS:
        engine = "claude"
    model = DEFAULT_MODELS[engine]

    try:
        review = call_ai(
            messages=[{"role": "user", "content": "今週の振り返りをお願いします。"}],
            system=prompt,
            engine=engine,
            model=model,
            max_tokens=1500,
        )
    except Exception as e:
        review = f"(AI 生成失敗: {e})"

    return {
        "generated_at": now.isoformat(),
        "since": cutoff,
        "completion_count": len(completions),
        "decision_count": len(decisions),
        "failure_count": len(failures),
        "focus_minutes_total": sum(by_cat.values()),
        "focus_by_category": by_cat,
        "review": review,
        "engine_used": engine,
        "model_used": model,
    }
