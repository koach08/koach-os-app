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
            not ((t.get("due_date") or "9999-12-31") < today),  # overdue=True first
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

    # 6. Coach バックログ + 今日向け簡易提案（3. Daily-Coach連携強化）
    try:
        from routers.productivity import _load_backlog, _load_life_blocks
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
        life_blocks = _load_life_blocks() if hasattr(globals().get('productivity', None), '_load_life_blocks') else []
        # 簡易: 今日の life load ヒント
        life_load_summary = "生活ブロック: " + ", ".join(b.get("title","") for b in (life_blocks or [])[:4]) if life_blocks else ""
    except Exception:
        backlog_items = []
        life_load_summary = ""

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

    # 1+2+4: メモからの自動完了認識 + 実績永続化 + 照合用データ
    memo_inferred = []
    try:
        from routers.memos import _infer_completions
        # 軽量（keyword）でまず走らせる。必要ならフロントから use_llm で再実行
        infer_result = _infer_completions(use_llm=False)
        memo_inferred = infer_result.get("applied", [])
    except Exception:
        memo_inferred = []

    # 予定 vs 実績 照合: 今日の予定のうち、完了もメモ言及もないものを missed として出す
    missed_items = []
    try:
        done_titles = {c.get("title", "").lower() for c in completions_today}
        done_titles |= {str(a.get("title", "")).lower() for a in memo_inferred if a.get("title")}
        for ev in schedule:
            t = str(ev.get("title", "")).lower()
            if t and not any(t in dt or dt in t for dt in done_titles):
                missed_items.append({"title": ev.get("title"), "start": ev.get("start"), "source": "calendar"})
        for t in tasks[:8]:
            if t.get("status") != "done":
                tl = str(t.get("title", "")).lower()
                if tl and not any(tl in dt or dt in tl for dt in done_titles):
                    missed_items.append({"title": t.get("title"), "due": t.get("due_date"), "source": "task"})
    except Exception:
        missed_items = []

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

    # 9a2. ノーショー・ガード — 当日必達 + 日付ズレ疑いを最上段で拾う
    guard_must = []
    guard_suspects = []
    try:
        from routers.guard import scan as _guard_scan
        g = _guard_scan(days=10)
        guard_must = g.get("must_not_miss", [])
        guard_suspects = g.get("date_suspects", [])
    except Exception:
        pass
    must_miss_text = (
        "\n".join(
            f"- {m['start_iso'][11:16]} {m['title']}" + (f" @ {m['location']}" if m.get("location") else "")
            + f"（{m['when']} {m['weekday']}）"
            for m in guard_must
        )
        if guard_must
        else "(なし)"
    )
    suspects_text = (
        "\n".join(f"- {s['title']}: {s['note']}" for s in guard_suspects)
        if guard_suspects
        else "(なし)"
    )

    # 9a3. 毎日の生活ロード (子育て・家事など平均負荷) — 空きから先に引く
    life_load_total = 0
    life_load_text = "(生活ロード未登録)"
    try:
        from routers.productivity import _life_load_summary
        life_load_total, life_load_text = _life_load_summary()
    except Exception:
        pass
    life_load_hours = round(life_load_total / 60, 1)

    # 9b. 今日の状態 (エネルギー) — 出力の強度とトーンを合わせる
    energy_band = "unknown"
    energy_hint = ""
    try:
        from routers.health_intake import state_hint
        sh = state_hint()
        energy_band = sh.get("energy_band", "unknown")
        energy_hint = sh.get("hint", "")
    except Exception:
        pass
    if energy_band == "low":
        energy_directive = (
            "本人は消耗している（低エネルギー）。今日の一手は3つでなく最大2つに絞り、"
            "重い深掘りは避ける。休息・睡眠を削らせない。無理に発破をかけず、"
            "『今日は守りでいい』と明示的に許可する。"
        )
    elif energy_band == "high":
        energy_directive = "本人は調子が良い（高エネルギー）。重めの一手を1つ混ぜて前進を後押ししてよい。"
    else:
        energy_directive = "エネルギーは平常。通常どおり今日3つを提案する。"
    energy_text = energy_hint or "(今日の状態データなし)"

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
    memo_text = (
        "\n".join(f"- {a.get('title','') or a.get('kind')}" for a in memo_inferred[:6])
        if memo_inferred
        else "(メモからの新規認識なし)"
    )
    missed_text = (
        "\n".join(f"- {m.get('title','')}" for m in missed_items[:5])
        if missed_items
        else "(未達疑いなし)"
    )

    prompt = f"""あなたは Koach OS。志柿のための reflective AI partner。
今は {now.strftime('%Y-%m-%d %H:%M (%A)')} 。
これから1日が始まる。生活を回すための朝のbriefingを出す。

## 今日ぜったい落とせない（会議・締切・入試など時刻付き重要予定・最優先で先頭に）
{must_miss_text}

## 日付ズレ疑い（タイトルの曜日と実際の曜日が食い違う＝1日ズレの可能性・要確認）
{suspects_text}

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

## メモから自動認識された実績（提出・完了を書いただけのものも含む）
{memo_text}

## 予定していたがまだ実績として拾えていないもの（注意）
{missed_text}

## 今日の状態（エネルギー）
{energy_text}
→ {energy_directive}

## 毎日の生活ロード（子育て・家事など時間割にできない平均負荷・合計 約{life_load_hours}時間/日）
{life_load_text}

## 出力ルール
- 「今日この時間にこれをやる」を組むとき、上の生活ロードの平均時間を空きから先に差し引いて、現実に収まる範囲だけで提案する。予定の隙間を全部作業で埋めない
- 冒頭でまず「今日ぜったい落とせない」を提示する（該当あれば）。時刻付きで、すっぽかさないよう念押しする
- 「日付ズレ疑い」が該当すれば、必ず「この予定、日付が1日ズレていないか確認を」と警告する
- 予定とバックログを見て「今日この時間にこれをやる」を提案する。時間帯（例: 10:00-11:30）を必ず添える。件数は上の『今日の状態』の指示に従う（平常3つ／低エネルギー最大2つ）
- 低エネルギーの日は、休息や家族の時間を削らないことを最優先にし、守りでよいと伝える
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
        "memo_inferred_completions": memo_inferred,
        "missed_items": missed_items[:8],
        "uni_pending": uni_pending,
        "autopilot_reports": autopilot_reports,
        "proposals_pending": proposals_pending,
        "email_pending": email_pending,
        "email_pending_total": email_pending_total,
        "energy_band": energy_band,
        "energy_hint": energy_hint,
        "must_not_miss": guard_must,
        "date_suspects": guard_suspects,
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
