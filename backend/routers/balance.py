"""
GET /api/balance — カテゴリ別バランスチェック。
完了ログ + Calendar の category 推定で、家族 / 健康 / クリエイティブ / 休息の確保状況を計算。
赤バッジが立つ閾値:
  - family: 過去7日で 5時間 未満
  - health: 過去7日で 0 完了 or 3日連続未消化
  - rest: 22時以降の完了ログが過去3日で 6時間以上（働きすぎ）
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data_manager import now_jst

router = APIRouter()

_JST = timezone(timedelta(hours=9))

# 保護ブロックの既定候補 (JST 時刻, 分)。上から順に空きを探す。
# family=夕方/週末昼、health=朝/夕方。title の keyword は _guess_category が拾える語に合わせる
# (確保後は次回の balance でそのカテゴリの実績として計上される＝ループが閉じる)。
PROTECT_DEFAULTS = {
    "family": {"label": "家族", "title": "家族の時間", "slots": [("18:00", 90), ("10:00", 120), ("19:30", 90)]},
    "health": {"label": "健康", "title": "運動・トレーニング", "slots": [("07:00", 60), ("17:00", 60), ("21:00", 45)]},
}


CATEGORY_KEYWORDS = {
    "family": ["家族", "保育園", "妻", "子", "親", "送り", "迎え", "夕食", "風呂"],
    "health": ["ブレイクダンス", "アクロバット", "運動", "筋トレ", "ジム", "ラン", "ヨガ", "ストレッチ", "睡眠"],
    "creative": ["執筆", "note", "記事", "ブログ", "AI 画像", "創作", "EGAKU"],
    "research": ["論文", "研究", "科研費", "査読"],
    "career": ["授業", "講義", "TA", "会議", "委員会", "学生"],
    "side_project": ["EGAKU", "crypto", "SpeakSmart", "個人開発"],
    "admin": ["事務", "メール", "申請", "提出"],
    "rest": ["休息", "昼寝", "リラックス"],
}


def _guess_category(title: str) -> str:
    t = title or ""
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return cat
    return "other"


def _parse_dt(iso: str):
    """タイムゾーン付き ISO を aware datetime に。終日 (YYYY-MM-DD) や失敗は None。"""
    if not iso or len(iso) <= 10:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except Exception:
        return None


def _busy_intervals(events: list[dict]) -> list[tuple[datetime, datetime]]:
    """時刻ありイベントの [開始, 終了] 区間。終日イベントは特定時刻を塞がない扱いで除外。"""
    out: list[tuple[datetime, datetime]] = []
    for ev in events:
        s = _parse_dt(ev.get("start_iso", ""))
        e = _parse_dt(ev.get("end_iso", ""))
        if s and e and e > s:
            out.append((s.astimezone(_JST), e.astimezone(_JST)))
    return out


def _is_free(s: datetime, e: datetime, busy: list[tuple[datetime, datetime]]) -> bool:
    return not any(s < b_e and e > b_s for (b_s, b_e) in busy)


def _protect_proposals(deficit_cats: list[str], now: datetime,
                       busy: list[tuple[datetime, datetime]]) -> list[dict]:
    """不足カテゴリごとに、今後 5 日の空き枠から具体ブロックを 1 つ提案する (承認制・書込なし)。"""
    proposals: list[dict] = []
    for cat in deficit_cats:
        spec = PROTECT_DEFAULTS.get(cat)
        if not spec:
            continue
        found = None
        # 翌日から 5 日先まで走査。family は週末(土日)を優先的に先へ。
        day_offsets = list(range(1, 6))
        if cat == "family":
            day_offsets.sort(key=lambda d: (now + timedelta(days=d)).weekday() < 5)
        for off in day_offsets:
            day = (now + timedelta(days=off)).date()
            for hhmm, dur in spec["slots"]:
                h, m = map(int, hhmm.split(":"))
                s = datetime(day.year, day.month, day.day, h, m, tzinfo=_JST)
                e = s + timedelta(minutes=dur)
                if _is_free(s, e, busy):
                    found = (s, e)
                    break
            if found:
                break
        if found:
            s, e = found
            proposals.append({
                "id": f"protect_{cat}_{s.strftime('%Y%m%dT%H%M')}",
                "category": cat,
                "label": spec["label"],
                "title": spec["title"],
                "start_iso": s.isoformat(),
                "end_iso": e.isoformat(),
                "when_text": s.strftime("%m/%d(%a) %H:%M") + "-" + e.strftime("%H:%M"),
            })
    return proposals


@router.get("/balance")
def balance(days: int = Query(7, ge=1, le=30)):
    now = now_jst()
    cutoff_date = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    # 完了ログを集約
    try:
        from routers.completions import _current_state
        all_state = _current_state()
        recent = [v for (_k, _r, d), v in all_state.items() if d >= cutoff_date]
    except Exception:
        recent = []

    # カテゴリ別件数 + 推定時間（1件 60分 + life-block 実時間）
    counts: dict[str, int] = {}
    for c in recent:
        cat = c.get("category") or _guess_category(c.get("title", ""))
        counts[cat] = counts.get(cat, 0) + 1

    # Calendar 実績（カテゴリは推定）
    cal_minutes: dict[str, int] = {}
    try:
        from gcal import is_configured, list_events_range
        if is_configured():
            start_str = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
            end_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            for ev in list_events_range(start_str, end_str):
                cat = _guess_category(ev.get("title", ""))
                try:
                    s = datetime.fromisoformat(ev["start_iso"].replace("Z", "+00:00"))
                    e = datetime.fromisoformat(ev["end_iso"].replace("Z", "+00:00"))
                    mins = max(0, int((e - s).total_seconds() / 60))
                    cal_minutes[cat] = cal_minutes.get(cat, 0) + mins
                except Exception:
                    continue
    except Exception:
        pass

    # 警告判定
    warnings: list[dict] = []
    family_minutes = cal_minutes.get("family", 0)
    if family_minutes < 300:  # 5時間未満
        warnings.append({
            "severity": "warn",
            "category": "family",
            "message": f"家族時間が過去{days}日で {family_minutes // 60} 時間。意識的にブロックを取ってください",
        })
    health_minutes = cal_minutes.get("health", 0)
    health_done = counts.get("health", 0)
    if health_done == 0 and health_minutes < 60:
        warnings.append({
            "severity": "warn",
            "category": "health",
            "message": f"健康ブロックが過去{days}日で {health_minutes} 分。再開予定のブレイクダンス・アクロバット枠を確保",
        })
    # 夜更かしチェック
    late_count = sum(
        1 for c in recent
        if (c.get("completed_at", "")[11:13] or "00").isdigit()
        and int(c.get("completed_at", "00:00")[11:13] or 0) >= 22
    )
    if late_count >= 5:
        warnings.append({
            "severity": "info",
            "category": "rest",
            "message": f"22時以降の作業完了が過去{days}日で {late_count} 件。睡眠優先",
        })

    # 保護ブロックの提案 (承認制) — family/health の不足時のみ、今後の空き枠から具体案を出す。
    # ここでは【提案のみ】。カレンダー書き込みは POST /balance/protect/confirm (本人の1タップ) だけが行う。
    deficit_cats = [w["category"] for w in warnings if w["category"] in PROTECT_DEFAULTS]
    protect_proposals: list[dict] = []
    if deficit_cats:
        try:
            from gcal import is_configured, list_events_range
            if is_configured():
                fstart = now.strftime("%Y-%m-%d")
                fend = (now + timedelta(days=7)).strftime("%Y-%m-%d")
                future_events = list_events_range(fstart, fend)
                busy = _busy_intervals(future_events)
                protect_proposals = _protect_proposals(deficit_cats, now, busy)
        except Exception:
            protect_proposals = []

    return {
        "days": days,
        "completions_by_category": counts,
        "calendar_minutes_by_category": cal_minutes,
        "warnings": warnings,
        "protect_proposals": protect_proposals,
    }


class ProtectConfirm(BaseModel):
    title: str
    start_iso: str
    end_iso: str
    category: str = "family"


@router.post("/balance/protect/confirm")
def protect_confirm(body: ProtectConfirm):
    """保護ブロックを実際にカレンダーへ確保する。実データ書き込みはこの明示操作でだけ起きる。"""
    from gcal import create_event, is_configured
    if not is_configured():
        raise HTTPException(status_code=400, detail="calendar not configured")
    try:
        ev = create_event(
            title=body.title,
            start_iso=body.start_iso,
            end_iso=body.end_iso,
            description="Koach OS が確保した保護ブロック（家族・健康を守る）。動かして構いません。",
            event_type="default",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"create_event failed: {e}")
    return {"ok": True, "event_id": ev.get("id", ""), "html_link": ev.get("htmlLink", "")}
