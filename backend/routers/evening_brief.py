"""
GET /api/evening-brief — 夜の振り返り。
今日の完了ログ + やり残し + AI 一行学び + 明日への繰越提案。
"""

from __future__ import annotations

from datetime import timedelta
from fastapi import APIRouter, Query

from data_manager import now_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()


@router.get("/evening-brief")
def evening_brief(engine: str = Query("claude")):
    now = now_jst()
    today_str = now.strftime("%Y-%m-%d")

    # 完了ログ
    try:
        from routers.completions import _current_state
        all_state = _current_state()
        completions_today = [v for (_k, _r, d), v in all_state.items() if d == today_str]
        completions_today.sort(key=lambda x: x.get("completed_at", ""))
    except Exception:
        completions_today = []

    # 今日の予定（実績比較用）
    try:
        from gcal import is_configured, get_events
        if is_configured():
            cal_today = [
                {
                    "id": e.get("id", ""),
                    "title": e.get("summary", ""),
                    "start": e.get("start", ""),
                    "location": e.get("location", ""),
                }
                for e in get_events(days_ahead=0)
            ]
        else:
            cal_today = []
    except Exception:
        cal_today = []

    done_ids = {c.get("ref_id") for c in completions_today if c.get("kind") == "calendar"}
    missed_calendar = [ev for ev in cal_today if ev["id"] and ev["id"] not in done_ids]

    # Coach バックログ
    try:
        from routers.productivity import _load_backlog
        backlog_done_ids = {c.get("ref_id") for c in completions_today if c.get("kind") == "backlog"}
        backlog_open = [b for b in _load_backlog() if not b.get("done")]
        backlog_left = [b for b in backlog_open if b.get("id") not in backlog_done_ids]
    except Exception:
        backlog_left = []

    # 明日の予定
    try:
        from gcal import get_events
        cal_tomorrow = [
            {"title": e.get("summary", ""), "start": e.get("start", "")}
            for e in get_events(days_ahead=1)
        ]
    except Exception:
        cal_tomorrow = []

    completion_text = (
        "\n".join(f"- {c.get('title','')}" for c in completions_today)
        if completions_today
        else "(今日は完了ログなし)"
    )
    missed_text = (
        "\n".join(f"- {ev['title']}" for ev in missed_calendar[:8])
        if missed_calendar
        else "(予定の取りこぼしなし)"
    )
    backlog_text = (
        "\n".join(f"- [{b.get('urgency','medium')}] {b.get('title','')}" for b in backlog_left[:10])
        if backlog_left
        else "(バックログ残なし)"
    )
    tomorrow_text = (
        "\n".join(
            f"- {ev['start'][11:16] if len(ev['start']) > 11 else '終日'} {ev['title']}"
            for ev in cal_tomorrow[:8]
        )
        if cal_tomorrow
        else "(明日の予定なし)"
    )

    prompt = f"""あなたは Koach OS。夜の振り返りを担当する reflective AI partner。
今は {now.strftime('%Y-%m-%d %H:%M (%A)')}。一日の終わり。

## 今日完了したこと ({len(completions_today)}件)
{completion_text}

## 予定で取りこぼしたもの
{missed_text}

## バックログ残り
{backlog_text}

## 明日の予定
{tomorrow_text}

## 出力ルール
- 「今日できたこと」を1〜2行で祝う（盛らない、淡々と）
- 「学び 1行」: 今日の動きから抽出。なければ書かない
- 「明日に繰越すなら」: バックログから1〜3個だけ選んで提案
- 「明日の最大の山」: 明日の予定で一番重いものを1つ指摘
- 200字以内。です/ます調。煽らない。抽象名詞「〜性」「重要性」「必要性」NG。一人称は「自分」"""

    if engine not in DEFAULT_MODELS:
        engine = "claude"
    model = DEFAULT_MODELS[engine]

    try:
        ai_brief = call_ai(
            messages=[{"role": "user", "content": "夜の振り返りをお願いします。"}],
            system=prompt,
            engine=engine,
            model=model,
            max_tokens=500,
        )
    except Exception as e:
        ai_brief = f"(AI brief 失敗: {e})"

    return {
        "generated_at": now.isoformat(),
        "completions": completions_today,
        "missed_calendar": missed_calendar,
        "backlog_left": [
            {"id": b.get("id"), "title": b.get("title"), "urgency": b.get("urgency", "medium")}
            for b in backlog_left[:10]
        ],
        "tomorrow": cal_tomorrow,
        "ai_brief": ai_brief,
        "engine_used": engine,
        "model_used": model,
    }
