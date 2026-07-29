"""
GET /api/measure — 提案→実行の測定ループ。

「autopilot が下書きを出す → 承認する → 実際に行動になる」の各段階を数字で見る。
propose-loop が本当に行動を生んでいるのか、それとも溜まるだけの劇場なのかを正直に測る。

測れるものだけを測る (でっち上げない):
  1. 下書き (kb_proposals): 生成 → 承認 / 却下 / 未処理。承認率・処理率・反応日数。
  2. 保護 (protect_log): 家族/健康ブロックを実際にカレンダーへ確保した回数 (balance の confirm が残す)。
  3. 完了 (completions): 直近の実行実績 (文脈用)。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median

from fastapi import APIRouter, Query

from data_manager import DATA_DIR, read_jsonl, now_jst

router = APIRouter()

# balance の protect_confirm が確保のたびに 1 行残す台帳 (append-only)。
PROTECT_LOG_FILE = DATA_DIR / "protect_log.jsonl"


def _parse(ts: str):
    try:
        return datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except Exception:
        return None


def _proposals_funnel(window_start: datetime) -> dict:
    """kb_proposals を id ごと最新に畳んでファネル化。"""
    from routers.proposals import _materialize
    items = list(_materialize().values())

    total = len(items)
    pending = promoted = rejected = 0
    decision_days: list[float] = []
    win_created = win_promoted = 0
    for e in items:
        st = e.get("status", "")
        if st == "pending":
            pending += 1
        elif st == "promoted":
            promoted += 1
        elif st == "rejected":
            rejected += 1
        created = _parse(e.get("created_at", ""))
        if created and created >= window_start:
            win_created += 1
        # 反応日数: created_at → updated_at (決着したものだけ)
        if st in ("promoted", "rejected"):
            updated = _parse(e.get("updated_at", ""))
            if created and updated and updated >= created:
                decision_days.append((updated - created).total_seconds() / 86400)
            if st == "promoted" and updated and updated >= window_start:
                win_promoted += 1

    decided = promoted + rejected
    return {
        "total": total,
        "pending": pending,
        "promoted": promoted,
        "rejected": rejected,
        "approval_rate": round(promoted / decided, 3) if decided else None,
        "triage_rate": round(decided / total, 3) if total else None,
        "median_days_to_decision": round(median(decision_days), 1) if decision_days else None,
        "window_created": win_created,
        "window_promoted": win_promoted,
    }


def _protect_execution(window_start: datetime) -> dict:
    """protect_log から、期間内に実際に確保した保護ブロックを集計。"""
    by_cat: dict[str, int] = {}
    confirmed = 0
    last = None
    for e in read_jsonl(PROTECT_LOG_FILE):
        at = _parse(e.get("confirmed_at", ""))
        if not at or at < window_start:
            continue
        confirmed += 1
        cat = e.get("category", "other")
        by_cat[cat] = by_cat.get(cat, 0) + 1
        if last is None or (at and _parse(last.get("confirmed_at", "")) and at >= _parse(last.get("confirmed_at", ""))):
            last = e
    return {"window_confirmed": confirmed, "by_category": by_cat, "last": last}


def _execution_context(window_start_date: str) -> dict:
    """completions を文脈として (期間内の完了総数とカテゴリ内訳)。"""
    try:
        from routers.completions import _current_state
        state = _current_state()
    except Exception:
        return {"completions": 0, "by_category": {}}
    total = 0
    by_cat: dict[str, int] = {}
    for (_kind, _ref, d), v in state.items():
        if d >= window_start_date:
            total += 1
            cat = v.get("category") or "other"
            by_cat[cat] = by_cat.get(cat, 0) + 1
    return {"completions": total, "by_category": by_cat}


def _verdict(prop: dict, prot: dict) -> str:
    """溜めてるだけ / 効いてる を正直に一言。"""
    if prop["total"] == 0:
        return "まだ下書きが生成されていません。水曜の consolidate が動けば測定が始まります。"
    if prop["pending"] >= 5 and (prop["triage_rate"] or 0) < 0.4:
        return f"未処理が {prop['pending']} 件溜まっています。承認/却下で捌かないと propose-loop が劇場になります。"
    parts = []
    if prop["approval_rate"] is not None:
        parts.append(f"下書きの承認率 {int(prop['approval_rate'] * 100)}%")
    if prot["window_confirmed"] > 0:
        parts.append(f"保護ブロックを {prot['window_confirmed']} 回確保")
    if not parts:
        return "決着した下書きがまだありません。捌けば承認率が出ます。"
    return "、".join(parts) + " — ループは行動まで届いています。"


@router.get("/measure")
def measure(days: int = Query(30, ge=1, le=180)):
    now = now_jst()
    window_start = now - timedelta(days=days)
    window_start_date = window_start.strftime("%Y-%m-%d")

    prop = _proposals_funnel(window_start)
    prot = _protect_execution(window_start)
    exe = _execution_context(window_start_date)

    return {
        "days": days,
        "generated_at": now.isoformat(),
        "proposals": prop,
        "protect": prot,
        "execution": exe,
        "verdict": _verdict(prop, prot),
    }
