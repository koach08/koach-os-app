"""
Assist — 横断アシスト系エンドポイント (既存データを集約して判断を助ける)。

- GET /api/next-action : 今この瞬間にやるべき一手を理由つきで1つ提示 (忖度しない)
- GET /api/triage      : 対応待ちメール + backlog + 期限切れタスクを1つに集約 (任意で AI 優先順位)
- GET /api/ai-usage    : worklog の engine タグ + routine 実行から AI 利用状況を集計

既存ローダを読むだけ。書き込み・既存ファイルへの干渉なし。
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Query

from data_manager import now_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()


# ─── 共通: 文脈収集 ───
def _today() -> str:
    return now_jst().strftime("%Y-%m-%d")


def _pending_emails(limit: int = 8) -> list[dict]:
    try:
        from routers.email_watch import _load, _is_pending, _days_since
        today = _today()
        out = []
        for it in (_load().get("items", {}) or {}).values():
            if not _is_pending(it, today):
                continue
            out.append({
                "subject": it.get("subject", "")[:80],
                "from": it.get("from", "")[:60],
                "urgency": it.get("urgency", "medium"),
                "deadline_date": it.get("deadline_date"),
                "days_since": _days_since(it.get("received_at", "")),
            })
        rank = {"high": 0, "medium": 1, "low": 2}
        out.sort(key=lambda x: (rank.get(x["urgency"], 1), -x["days_since"]))
        return out[:limit]
    except Exception:
        return []


def _open_backlog(limit: int = 12) -> list[dict]:
    try:
        from routers.productivity import _load_backlog
        rank = {"high": 0, "medium": 1, "low": 2}
        out = [
            {"title": b.get("title", ""), "category": b.get("category", ""),
             "urgency": b.get("urgency", "medium"), "due_date": b.get("due_date")}
            for b in _load_backlog() if not b.get("done")
        ]
        out.sort(key=lambda x: (rank.get(x["urgency"], 1), x.get("due_date") or "9999"))
        return out[:limit]
    except Exception:
        return []


def _overdue_tasks(limit: int = 12) -> list[dict]:
    try:
        from routers.tasks import _materialize_state
        today = _today()
        out = []
        for t in _materialize_state().values():
            if t.get("status") == "done":
                continue
            due = t.get("due_date")
            out.append({
                "title": t.get("title", ""),
                "due_date": due,
                "status": t.get("status", "todo"),
                "overdue": bool(due and due < today),
            })
        out.sort(key=lambda x: (not x["overdue"], x.get("due_date") or "9999"))
        return out[:limit]
    except Exception:
        return []


def _todays_calendar(remaining_only: bool = True) -> list[dict]:
    try:
        from gcal import is_configured, get_events
        if not is_configured():
            return []
        now_iso = now_jst().isoformat()
        out = []
        for e in get_events(days_ahead=0) or []:
            start = e.get("start", "") or ""
            if remaining_only and start and "T" in start and start < now_iso:
                continue
            out.append({"title": e.get("summary", ""), "start": start, "location": e.get("location", "")})
        return out
    except Exception:
        return []


def _recent_worklog(limit: int = 5) -> list[dict]:
    try:
        from routers.work_log import _materialize as _wl
        recent = sorted(_wl().values(), key=lambda w: w.get("date", ""), reverse=True)[:limit]
        return [{"date": w.get("date", ""), "title": w.get("title", ""), "category": w.get("category", "")} for w in recent]
    except Exception:
        return []


# ─── /next-action ───
@router.get("/next-action")
def next_action(engine: str = Query("claude")):
    now = now_jst()
    cal = _todays_calendar(remaining_only=True)
    emails = _pending_emails(6)
    backlog = _open_backlog(8)
    tasks = _overdue_tasks(8)
    worklog = _recent_worklog(5)

    ctx = {
        "now": now.strftime("%Y-%m-%d %H:%M (%A)"),
        "remaining_calendar": cal,
        "pending_emails": emails,
        "open_backlog": backlog,
        "tasks": tasks,
        "recent_done": worklog,
    }

    prompt = (
        f"今は {ctx['now']}。以下のデータを見て、『今この瞬間にやるべき一手』を1つだけ選んでください。\n\n"
        f"=== 今日の残り予定 ===\n{json.dumps(cal, ensure_ascii=False)}\n\n"
        f"=== 対応待ちメール ===\n{json.dumps(emails, ensure_ascii=False)}\n\n"
        f"=== 未完バックログ ===\n{json.dumps(backlog, ensure_ascii=False)}\n\n"
        f"=== 期限つきタスク ===\n{json.dumps(tasks, ensure_ascii=False)}\n\n"
        f"=== 直近やり終えた事 ===\n{json.dumps(worklog, ensure_ascii=False)}\n"
    )
    system = (
        "あなたは志柿の相棒 AI。今やるべき一手を1つだけ即断で薦める。\n"
        "ルール:\n"
        "- 出力は『■ 今やる一手』(1行) → 『■ 理由』(2-3行) → 『■ 次の候補』(1-2個) の順\n"
        "- 締切の近さ・放置日数・次の予定までの空き時間を根拠に。数字を引く\n"
        "- 迎合しない。先送りしている物があれば名指しで指摘する\n"
        "- 抽象名詞「〜性」、em ダッシュ、過度な絵文字は使わない。です/ます調。一人称は「自分」"
    )
    eng = engine if engine in DEFAULT_MODELS else "claude"
    try:
        out = call_ai(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            engine=eng,
            model=DEFAULT_MODELS[eng],
            max_tokens=600,
        )
    except Exception as e:
        out = f"(AI 生成失敗: {e})"

    return {
        "generated_at": now.isoformat(),
        "recommendation": out,
        "engine_used": eng,
        "context_counts": {
            "remaining_calendar": len(cal),
            "pending_emails": len(emails),
            "open_backlog": len(backlog),
            "tasks": len(tasks),
        },
    }


# ─── /triage ───
@router.get("/triage")
def triage(ai: bool = Query(False), engine: str = Query("claude")):
    emails = _pending_emails(20)
    backlog = _open_backlog(20)
    tasks = _overdue_tasks(20)

    result: dict = {
        "generated_at": now_jst().isoformat(),
        "emails": emails,
        "backlog": backlog,
        "overdue_tasks": [t for t in tasks if t.get("overdue")],
        "tasks": tasks,
        "counts": {
            "emails": len(emails),
            "backlog": len(backlog),
            "overdue_tasks": len([t for t in tasks if t.get("overdue")]),
        },
    }

    if ai:
        prompt = (
            "以下の『未対応』を全部見て、今週片付ける優先順位トップ10を作ってください。\n"
            "各項目: 『順位. [種別] 内容 — なぜ今か(1行)』。\n\n"
            f"=== 対応待ちメール ===\n{json.dumps(emails, ensure_ascii=False)}\n\n"
            f"=== バックログ ===\n{json.dumps(backlog, ensure_ascii=False)}\n\n"
            f"=== タスク ===\n{json.dumps(tasks, ensure_ascii=False)}\n"
        )
        system = (
            "あなたは志柿の秘書 AI。散らばった未対応を俯瞰し、現実的な優先順位をつける。"
            "締切・放置日数を根拠に。迎合せず、先送り常習のものは指摘する。"
            "抽象名詞「〜性」と em ダッシュは使わない。です/ます調。"
        )
        eng = engine if engine in DEFAULT_MODELS else "claude"
        try:
            result["ai_priorities"] = call_ai(
                messages=[{"role": "user", "content": prompt}],
                system=system,
                engine=eng,
                model=DEFAULT_MODELS[eng],
                max_tokens=900,
            )
            result["engine_used"] = eng
        except Exception as e:
            result["ai_priorities"] = f"(AI 生成失敗: {e})"

    return result


# ─── /ai-usage ───
@router.get("/ai-usage")
def ai_usage(days: int = Query(90, ge=1, le=3650)):
    # worklog ベース
    wl_by_engine: dict = {}
    wl_by_category: dict = {}
    try:
        from routers.work_log import work_log_stats
        st = work_log_stats(days)
        wl_by_engine = st.get("by_engine", {})
        wl_by_category = st.get("engine_by_category", {})
    except Exception:
        pass

    # routine 実行ベース
    run_by_engine: dict = {}
    try:
        from routers.routines import RUNS_FILE
        from data_manager import read_jsonl
        for r in read_jsonl(RUNS_FILE):
            eng = r.get("engine_used") or "?"
            run_by_engine[eng] = run_by_engine.get(eng, 0) + 1
    except Exception:
        pass

    return {
        "days": days,
        "worklog_by_engine": wl_by_engine,
        "worklog_engine_by_category": wl_by_category,
        "routine_runs_by_engine": run_by_engine,
    }
