"""
GET /api/guard/scan — ノーショー・ガード。
「すっぽかし」の2つの原因を先回りで拾う:
  1. 通知欠落: 会議/締切/入試など重要予定なのに「前日通知」が付いていない。
  2. 日付ズレ: タイトルの曜日(例「(火)」)と、実際の日付の曜日が食い違う=1日ズレ疑い。
そして「今日ぜったい落とせない」時刻付き重要予定を前出しする。

検知は読み取りのみ。実カレンダーへの通知追加は POST /guard/fix-reminders
(本人の1タップ) だけが行う。自動ジョブは絶対に書かない。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data_manager import now_jst

router = APIRouter()

# 曜日マーカー: 月=0 … 日=6 (Python date.weekday() と一致)
_WD = {"月": 0, "火": 1, "水": 2, "木": 3, "金": 4, "土": 5, "日": 6}


def _weekday_in_text(text: str) -> int | None:
    """タイトル等から曜日マーカーを1つ拾う。「(火)」「（火）」「火曜」を見る。"""
    if not text:
        return None
    for ch, idx in _WD.items():
        if f"({ch})" in text or f"（{ch}）" in text or f"{ch}曜" in text:
            return idx
    return None


def _has_day_before(reminders: dict) -> bool:
    """前日 (1440分以上前) の通知が1つでもあるか。useDefault は不明扱いで False。"""
    if not isinstance(reminders, dict):
        return False
    if reminders.get("useDefault"):
        # Google 既定通知の中身は取れないので「保証されない」= 手薄側に倒す
        return False
    for r in reminders.get("overrides", []) or []:
        if int(r.get("minutes", 0)) >= 1440:
            return True
    return False


def _wd_ja(idx: int) -> str:
    return "月火水木金土日"[idx] if 0 <= idx <= 6 else "?"


@router.get("/guard/scan")
def scan(days: int = Query(10, ge=1, le=30)):
    now = now_jst()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    end = (now + timedelta(days=days + 1)).strftime("%Y-%m-%d")

    try:
        from gcal import list_events_range, is_configured, IMPORTANT_EVENT_TYPES
        if not is_configured():
            return {"configured": False, "must_not_miss": [], "date_suspects": [], "reminder_gaps": []}
        events = list_events_range(today, end)
    except Exception as e:
        return {"configured": False, "error": str(e), "must_not_miss": [], "date_suspects": [], "reminder_gaps": []}

    must_not_miss: list[dict] = []
    date_suspects: list[dict] = []
    reminder_gaps: list[dict] = []

    for ev in events:
        title = ev.get("title", "")
        start_iso = ev.get("start_iso", "")
        etype = ev.get("event_type", "default")
        date_part = start_iso[:10]
        important = etype in IMPORTANT_EVENT_TYPES

        # 1. 日付ズレ疑い: タイトルの曜日 vs 実日付の曜日
        wd_text = _weekday_in_text(title + " " + ev.get("description", ""))
        if wd_text is not None and len(date_part) == 10:
            try:
                actual_wd = datetime.fromisoformat(date_part).weekday()
                if actual_wd != wd_text:
                    date_suspects.append({
                        "id": ev.get("id"), "slot": ev.get("slot"), "calendar_id": ev.get("calendar_id"),
                        "title": title, "start_iso": start_iso,
                        "written_weekday": _wd_ja(wd_text), "actual_weekday": _wd_ja(actual_wd),
                        "note": f"タイトルは({_wd_ja(wd_text)})だが {date_part} は{_wd_ja(actual_wd)}曜。1日ズレの疑い",
                    })
            except Exception:
                pass

        # 2. 当日/明日の必達 (時刻あり重要予定)
        if important and not ev.get("all_day") and date_part in (today, tomorrow):
            must_not_miss.append({
                "id": ev.get("id"), "title": title, "start_iso": start_iso,
                "event_type": etype, "location": ev.get("location", ""),
                "when": date_part, "weekday": _wd_ja(datetime.fromisoformat(date_part).weekday()) if len(date_part) == 10 else "",
            })

        # 3. 通知欠落: 重要予定なのに前日通知なし
        if important and not _has_day_before(ev.get("reminders", {})):
            reminder_gaps.append({
                "id": ev.get("id"), "slot": ev.get("slot"), "calendar_id": ev.get("calendar_id"),
                "title": title, "start_iso": start_iso, "event_type": etype,
            })

    must_not_miss.sort(key=lambda x: x.get("start_iso", ""))
    reminder_gaps.sort(key=lambda x: x.get("start_iso", ""))
    date_suspects.sort(key=lambda x: x.get("start_iso", ""))
    return {
        "configured": True,
        "days": days,
        "must_not_miss": must_not_miss,
        "date_suspects": date_suspects,
        "reminder_gaps": reminder_gaps,
    }


class FixReminders(BaseModel):
    event_id: str
    event_type: str = "meeting"
    calendar_id: str = "primary"
    slot: int = 1


@router.post("/guard/fix-reminders")
def fix_reminders(body: FixReminders):
    """重要予定に前日通知を付ける (本人の1タップ)。予定の中身は変えず通知だけ加える。"""
    try:
        from gcal import set_event_reminders
        result = set_event_reminders(
            body.event_id, body.event_type,
            calendar_id=body.calendar_id, slot=body.slot,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"set_event_reminders failed: {e}")
    return {"ok": True, "reminders_set": result.get("_reminders_set", [])}
