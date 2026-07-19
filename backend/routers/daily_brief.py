"""
GET /api/daily-brief — 朝1画面で生活を回すためのDaily Brief
- Gcal 今日の予定
- 直近の決定ログ
- 直近の会話トピック
- L3 介入：「今日3つに絞って」AI問いかけ
"""

import json
from datetime import timedelta, datetime
from fastapi import APIRouter, Query

from gcal import is_configured, get_events
from data_manager import (
    read_jsonl,
    LOGS_FILE,
    DECISIONS_FILE,
    FAILURES_FILE,
    TASKS_FILE,
    MEMOS_FILE,
    DATA_DIR,
    now_jst,
)
from router import call_ai, DEFAULT_MODELS, AVAILABLE_MODELS

router = APIRouter()


def _format_event(ev: dict) -> dict:
    """Calendar event -> minimal frontend-friendly shape."""
    return {
        "id": ev.get("id", ""),
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


def _autopilot_today(today: str) -> list[dict]:
    """今朝の autopilot 結論を job ごと最新で返す。裏で集めた結論を朝ブリーフに束ねる (情報サイロ解消)。"""
    latest: dict[str, dict] = {}
    for m in read_jsonl(MEMOS_FILE):
        if m.get("source") != "autopilot":
            continue
        if str(m.get("created_at", ""))[:10] != today:
            continue
        job = m.get("autopilot_job", "autopilot")
        latest[job] = m  # 追記順＝新しいものが後 → job ごと最新が残る
    JOB_JA = {"morning-prep": "朝の準備", "email-triage": "メール", "backlog-progress": "積み残し"}
    out = []
    for job, m in latest.items():
        body = str(m.get("content", ""))
        # 先頭の "🤖 [autopilot:job] mm/dd HH:MM\n\n" ヘッダを落とし本文だけに
        if "\n\n" in body:
            body = body.split("\n\n", 1)[1]
        out.append({
            "job": job,
            "label": JOB_JA.get(job, job),
            "summary": body.strip()[:500],
            "at": str(m.get("created_at", ""))[11:16],
        })
    # 表示順: 朝の準備 → メール → 積み残し
    order = {"morning-prep": 0, "email-triage": 1, "backlog-progress": 2}
    out.sort(key=lambda x: order.get(x["job"], 9))
    return out


def _proposals_pending() -> list[dict]:
    """承認待ちの構造化下書き。朝に「決めるだけ」で片付く昇格候補を見せる。"""
    try:
        from routers.proposals import _materialize
    except Exception:
        return []
    out = []
    for p in _materialize().values():
        if p.get("status") != "pending":
            continue
        out.append({
            "id": p.get("id", ""),
            "title": p.get("title", "")[:80],
            "kind": p.get("kind", "decision"),
            "domain": p.get("domain", "personal"),
        })
    return out


def _email_pending(limit: int = 4) -> tuple[list[dict], int]:
    """対応待ちメール (snooze/返信済み除外)。ネットワーク無し、保存済み状態を読むだけ。"""
    try:
        # 明示引数で呼ぶ (route を素で呼ぶと Query() 既定が FieldInfo になり内部で落ちる)
        from routers.email_watch import list_pending
        data = list_pending(overdue_only=False, overdue_days=2)
    except Exception:
        return [], 0
    items = data.get("items", []) if isinstance(data, dict) else []
    out = []
    for it in items[:limit]:
        out.append({
            "id": it.get("id", ""),
            "subject": str(it.get("subject", ""))[:70],
            "from": str(it.get("from", ""))[:50],
            "urgency": it.get("urgency", "medium"),
            "days": it.get("days_since_received", 0),
        })
    return out, len(items)


DAILY_BRIEF_CACHE = DATA_DIR / "daily_brief_cache.json"


def _load_cache() -> dict:
    if not DAILY_BRIEF_CACHE.exists():
        return {}
    try:
        return json.loads(DAILY_BRIEF_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict):
    try:
        DAILY_BRIEF_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


@router.get("/daily-brief")
def daily_brief(
    engine: str = Query("claude", description="claude/gpt/grok/gemini/venice/perplexity/groq"),
    model: str | None = Query(None, description="override model id (optional)"),
    force: bool = Query(False, description="true ならキャッシュ無視で再生成"),
):
    """
    朝1画面で出すDaily Brief。
    schedule + decisions + topics + failures + AI問いかけ を構造化JSONで返す。

    同日中は engine 単位でキャッシュを返す (タブ切替で毎回生成しない)。
    force=true で再生成。
    """
    now = now_jst()
    today_key = now.strftime("%Y-%m-%d")
    cache_key = f"{today_key}::{engine}::{model or 'default'}"
    # NOTE: schedule / completions / backlog などは毎回 fresh で取る (Calendar 削除や完了チェックが即反映されるため)
    # キャッシュするのは ai_brief だけ。下で生成パートで再利用する

    # 1. Gcal 予定（今日 / 明日 / 今週）
    if is_configured():
        events_raw = get_events(days_ahead=0)
        schedule = [_format_event(ev) for ev in events_raw]
        tomorrow_raw = get_events(days_ahead=1)
        schedule_tomorrow = [_format_event(ev) for ev in tomorrow_raw]
        # 今週分（今日含む7日）
        try:
            from gcal import list_upcoming_events
            week_raw = list_upcoming_events(days_ahead=7)
            schedule_week = [
                {
                    "title": ev["title"],
                    "start": ev["start_iso"],
                    "end": ev["end_iso"],
                    "location": ev["location"],
                    "all_day": ev["all_day"],
                    "event_type": ev["event_type"],
                }
                for ev in week_raw
            ]
        except Exception:
            schedule_week = []
        gcal_status = "ok"
    else:
        schedule = []
        schedule_tomorrow = []
        schedule_week = []
        gcal_status = "not_configured"

    # 2. 直近の決定ログ
    decisions = _recent_decisions(days=3, limit=5)

    # 3. 直近の話題
    topics = _recent_topics(limit=5)

    # 4. 失敗からの学び
    failures = _recent_failures(limit=2)

    # 5. オープンタスク
    tasks = _open_tasks()

    # 6. Coach バックログ（未完 + defer_until 過ぎたものだけ）
    try:
        from routers.productivity import _load_backlog
        today_iso = now.strftime("%Y-%m-%d")
        backlog_items = [
            {
                "id": b.get("id", ""),
                "title": b.get("title", ""),
                "category": b.get("category", "other"),
                "urgency": b.get("urgency", "medium"),
                "estimated_minutes": b.get("estimated_minutes", 60),
                "needs_ai": b.get("needs_ai", False),
                "due_date": b.get("due_date"),
                "defer_until": b.get("defer_until"),
            }
            for b in _load_backlog()
            if not b.get("done")
            and (not b.get("defer_until") or b["defer_until"] <= today_iso)
        ]
    except Exception:
        backlog_items = []

    # 7. 今日の完了ログ
    try:
        from routers.completions import _current_state
        today_str = now.strftime("%Y-%m-%d")
        completions_today = [
            v for (_k, _r, d), v in _current_state().items() if d == today_str
        ]
        completions_today.sort(key=lambda x: x.get("completed_at", ""))
    except Exception:
        completions_today = []

    # 8. 大学メールの未反映 (uni-inbox) — カレンダー未登録の締切・予定。朝ブリーフに含めて見落とし防止
    try:
        from routers.uni_inbox import _materialize as _uni_materialize
        _today = now.strftime("%Y-%m-%d")
        uni_pending = []
        for it in _uni_materialize().values():
            if it.get("status") != "pending":
                continue
            uni_pending.append({
                "id": it.get("id", ""),
                "title": it.get("title", ""),
                "start_iso": it.get("start_iso", ""),
                "event_type": it.get("event_type", "default"),
                "confidence": it.get("confidence", "medium"),
                "day": str(it.get("start_iso", ""))[:10],
            })
        uni_pending.sort(key=lambda x: x.get("start_iso", "") or "9999")
    except Exception:
        uni_pending = []
        _today = now.strftime("%Y-%m-%d")

    def _uni_line(u: dict) -> str:
        d = u["day"] or "日付未定"
        tm = (u["start_iso"][11:16] + " ") if "T" in u["start_iso"] else ""
        tag = {"deadline": "〆", "committee": "委", "meeting": "会"}.get(u["event_type"], "・")
        return f"- [{tag}] {d} {tm}{u['title'][:40]}"

    upcoming_uni = [u for u in uni_pending if (u["day"] or "9999") >= _today]
    uni_text = "\n".join(_uni_line(u) for u in upcoming_uni[:8]) if upcoming_uni else "(未反映なし)"

    # 9. 裏で集めた結論を朝に束ねる (司令塔化) — autopilot / 承認待ち / 対応待ちメール
    today_str2 = now.strftime("%Y-%m-%d")
    autopilot_reports = _autopilot_today(today_str2)
    proposals_pending = _proposals_pending()
    email_pending, email_pending_total = _email_pending(limit=4)

    autopilot_text = (
        "\n\n".join(f"### {r['label']} ({r['at']})\n{r['summary']}" for r in autopilot_reports)
        if autopilot_reports
        else "(今朝の自動調査なし)"
    )
    proposals_text = (
        "\n".join(f"- [{p['kind']}/{p['domain']}] {p['title']}" for p in proposals_pending[:6])
        if proposals_pending
        else "(承認待ちなし)"
    )
    email_pending_text = (
        "\n".join(
            f"- [{e['urgency']}] {e['from']}: {e['subject']} ({e['days']}日経過)"
            for e in email_pending
        )
        if email_pending
        else "(対応待ちメールなし)"
    )

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
    backlog_text = (
        "\n".join(
            f"- [{b['urgency']}] [{b['category']}] {b['title']} (推定{b['estimated_minutes']}分)"
            for b in backlog_items[:15]
        )
        if backlog_items
        else "(Coach バックログ空)"
    )
    completion_text = (
        "\n".join(f"- {c.get('title','')}" for c in completions_today)
        if completions_today
        else "(今日まだ完了なし)"
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

## Coach バックログ
{backlog_text}

## 大学の未反映（カレンダー未登録の締切・予定 / 見落とし注意）
{uni_text}

## 今朝わたし(autopilot)が裏で調べた結論（再調査せず、ここを起点に）
{autopilot_text}

## 対応待ちメール（返信・処理が止まっている / 全{email_pending_total}件）
{email_pending_text}

## 承認待ちの下書き（決めるだけで片付く昇格候補）
{proposals_text}

## 今日すでに完了したこと
{completion_text}

## 出力ルール
- 予定とバックログを見て「今日この時間にこれをやる」を3つだけ提案する。時間帯（例: 10:00-11:30）を必ず添える
- 今朝の autopilot 結論は既に調べ済み。同じ調査を繰り返さず、その結論を前提に今日の一手へ繋げる
- 大学の未反映に締切が近いもの / 数日止まっている対応待ちメールがあれば、今日やる3つ or 問いに必ず反映する
- 予定の隙間時間を具体的にどう使うかブロックで示す
- 直近の決定を1つだけリマインド（忘れがちなものを優先）
- L3 介入レベル: 戦略的視点で1つ問いを立てる（「本当に必要？」など）
- 完了済みは祝うが繰り返さない
- 250字以内。箇条書き
- 日本語、です/ます調、煽らない、抽象名詞「〜性」は使わない"""

    # Resolve model: explicit > engine default > claude default
    if engine not in DEFAULT_MODELS:
        engine = "claude"
    resolved_model = model or DEFAULT_MODELS.get(engine, DEFAULT_MODELS["claude"])

    # AI brief は同日中キャッシュ (タブ切替で再生成しない)
    # ※キャッシュ判定の prompt_hash: schedule / backlog の中身が大きく変わったらキャッシュ無効
    import hashlib as _hl
    prompt_hash = _hl.md5(prompt.encode("utf-8")).hexdigest()[:8]
    cache_key_full = f"{cache_key}::{prompt_hash}"

    ai_brief = ""
    brief_from_cache = False
    if not force:
        cache = _load_cache()
        cached = cache.get(cache_key_full)
        if cached and cached.get("ai_brief"):
            ai_brief = cached["ai_brief"]
            brief_from_cache = True

    if not ai_brief:
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

    result = {
        "generated_at": now.isoformat(),
        "schedule": schedule,
        "schedule_tomorrow": schedule_tomorrow,
        "schedule_week": schedule_week,
        "gcal_status": gcal_status,
        "decisions": decisions,
        "topics": topics,
        "failures": failures,
        "tasks": tasks,
        "backlog": backlog_items,
        "completions_today": completions_today,
        "uni_pending": uni_pending,
        "autopilot_reports": autopilot_reports,
        "proposals_pending": proposals_pending,
        "email_pending": email_pending,
        "email_pending_total": email_pending_total,
        "ai_brief": ai_brief,
        "engine_used": engine,
        "model_used": resolved_model,
        "from_cache": brief_from_cache,
    }
    # AI brief だけキャッシュ (失敗時 / 既にキャッシュから返した時は書かない)
    if not brief_from_cache and not ai_brief.startswith("(AI brief 失敗"):
        cache = _load_cache()
        cutoff = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        cache = {k: v for k, v in cache.items() if k.split("::")[0] >= cutoff}
        cache[cache_key_full] = {"ai_brief": ai_brief, "generated_at": now.isoformat()}
        _save_cache(cache)
    return result
