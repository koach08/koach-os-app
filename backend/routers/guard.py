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


def _is_multiday_period(ev: dict) -> bool:
    """複数日にまたがる終日イベント (夏季休業・受理期間など) か。予定でなく期間なので除外用。"""
    if not ev.get("all_day"):
        return False
    s = (ev.get("start_iso", "") or "")[:10]
    e = (ev.get("end_iso", "") or "")[:10]
    if len(s) != 10 or len(e) != 10:
        return False
    try:
        return (datetime.fromisoformat(e) - datetime.fromisoformat(s)).days > 1
    except Exception:
        return False


def _norm_title(t: str) -> str:
    """比較用にタイトルから空白を落とす。"""
    return "".join((t or "").split()).replace("\u3000", "")


def _strip_paren(t: str) -> str:
    """括弧書きを落とす。「〜提出期限(修士1年次)」と「〜提出期限」を同じ扱いにする用。"""
    import re
    return re.sub(r"[(（][^)）]*[)）]", "", t or "").strip()


def _same_series(a: str, b: str) -> bool:
    """同じ会議シリーズとみなせるか。片方がもう片方の先頭に一致すればよい。

    大学アカウント側は「教授会」だけ、Gmail 側は
    「教授会 修士・博士(10月)合格者決定、…」のように議題つきで入っていることがある。
    """
    na, nb = _norm_title(a), _norm_title(b)
    if len(na) < 2 or len(nb) < 2:
        return False
    return na.startswith(nb) or nb.startswith(na)


def _cal_key(ev: dict) -> tuple:
    return (ev.get("slot"), ev.get("calendar_id"))


def _series_on_day(events: list[dict], ref: dict, day: str) -> bool:
    """ref と同じカレンダー・同じシリーズの予定が day にもあるか。"""
    for e in events:
        if _cal_key(e) != _cal_key(ref):
            continue
        if (e.get("start_iso") or "")[:10] != day:
            continue
        if _same_series(e.get("title", ""), ref.get("title", "")):
            return True
    return False


def _cross_calendar_conflicts(events: list[dict], max_gap_days: int = 21) -> list[dict]:
    """同じ会議が別カレンダーに別の日で入っているものを拾う。

    大学アカウントと Gmail の両方に学事予定が入っていて、日程変更のときに
    片方だけ直っていないと、古い日付が「今日の予定」に出てくる。
    実際 2026-08 の教授会が大学側 8/20・Gmail 側 8/28 で食い違っていた。

    誤検知を避けるため、次を全部満たすものだけ挙げる:
      - 別のカレンダー同士
      - 開始時刻 (HH:MM) が一致 (終日同士も可)
      - タイトルが同じシリーズ
      - 日付が違い、かつ離れすぎていない (既定 21 日以内 = 月次の別の回は拾わない)
      - どちらの日にも「相手カレンダーの同じシリーズ」が居ない (単に連続した別の回ではない)
    """
    cand = [e for e in events
            if (e.get("start_iso") or "") and not _is_multiday_period(e)]
    out: list[dict] = []
    seen: set[tuple] = set()
    for i, a in enumerate(cand):
        for b in cand[i + 1:]:
            if _cal_key(a) == _cal_key(b):
                continue
            sa, sb = a["start_iso"], b["start_iso"]
            da, db = sa[:10], sb[:10]
            if da == db:
                continue
            if sa[11:16] != sb[11:16]:  # 時刻が違えば別の会議
                continue
            if not _same_series(a.get("title", ""), b.get("title", "")):
                continue
            try:
                gap = abs((datetime.fromisoformat(da) - datetime.fromisoformat(db)).days)
            except Exception:
                continue
            if gap == 0 or gap > max_gap_days:
                continue
            if _series_on_day(cand, a, db) or _series_on_day(cand, b, da):
                continue  # 相手側にも同じ日の回がある = 連続した別の回
            # 同じ食い違いは 1 件だけ出す。片方のカレンダーに複製が 2 件あると
            # ペアが 2 通りできて同じ指摘が並ぶので、id ではなく
            # 「短い方のタイトル + 2 つの日付」で畳む。
            # 「〜提出期限」と「〜提出期限(修士1年次)」のように括弧書きだけ違う
            # 表記ゆれも同じ指摘なので、括弧の中は落としてから比べる。
            short = _strip_paren(min(_norm_title(a.get("title", "")),
                                     _norm_title(b.get("title", "")), key=len))
            key = (short, min(da, db), max(da, db))
            if key in seen:
                continue
            seen.add(key)
            # 議題が書いてある方を「詳しい側」として先に出す
            rich, plain = (a, b) if len(a.get("title", "")) >= len(b.get("title", "")) else (b, a)
            out.append({
                "id": plain.get("id"), "slot": plain.get("slot"),
                "calendar_id": plain.get("calendar_id"),
                "title": plain.get("title"), "start_iso": plain.get("start_iso"),
                "kind": "cross_calendar",
                "other_id": rich.get("id"), "other_slot": rich.get("slot"),
                "other_calendar_id": rich.get("calendar_id"),
                "other_title": rich.get("title"), "other_start_iso": rich.get("start_iso"),
                "note": (
                    f"同じ予定がカレンダーで食い違っている: "
                    f"{plain.get('calendar_id')} は {(plain.get('start_iso') or '')[:10]}、"
                    f"{rich.get('calendar_id')} は {(rich.get('start_iso') or '')[:10]}。"
                    f"{gap}日ズレ。日程変更が片方だけ反映されていない疑い"
                ),
            })
    return out


_ONLINE_MARKERS = (
    "zoom", "teams", "webex", "meet", "オンライン", "online", "ウェビナー",
    "webinar", "リモート", "配信", "http",
)


def _is_onsite(location: str) -> bool:
    """その場所に体を運ぶ必要があるか。Zoom 等が書いてあるだけなら移動は要らない。"""
    loc = (location or "").strip().lower()
    if not loc or loc == "none":
        return False
    return not any(m in loc for m in _ONLINE_MARKERS)


def _overlaps(events: list[dict]) -> list[dict]:
    """同じ時間帯に 2 つ以上の予定が入っているものを拾う。

    「重なると混乱してテンパる」ので、当日になって気づくのではなく
    前もって出す。実際 2026-09-03 は外国語教育将来構想 WG (301会議室・対面)
    と FD 研修 (Zoom) が 16:00-16:15 重なり、その 30 分後に保育園の迎えだった。

    締切は「その時間そこに居る」予定ではないので数えない。締切ブロックを
    数えると 12:00 の締切と 12:00 の会議が毎回ぶつかったことになる。
    終日と期間ものも対象外。
    """
    timed = [
        e for e in events
        if not e.get("all_day") and not _is_multiday_period(e)
        and len(e.get("start_iso") or "") > 16
        and e.get("event_type") != "deadline"
    ]

    def span(e: dict) -> tuple[str, str]:
        s = e.get("start_iso") or ""
        return s, (e.get("end_iso") or s)

    out: list[dict] = []
    seen: set[tuple] = set()
    for i, a in enumerate(timed):
        sa, ea = span(a)
        for b in timed[i + 1:]:
            sb, eb = span(b)
            if sa[:10] != sb[:10]:
                continue
            if not (sa < eb and sb < ea):  # 重なっていない
                continue
            # 同じ予定が別カレンダーに入っているだけなら重なりではない。
            # 大学側は「教授会」、Gmail 側は「教授会 研究生受入れ決定」のように
            # 詳しさが違うので、完全一致では拾えず _same_series で見る。
            if sa == sb and _same_series(a.get("title", ""), b.get("title", "")):
                continue
            key = tuple(sorted([f"{_norm_title(a.get('title',''))}@{sa}",
                                f"{_norm_title(b.get('title',''))}@{sb}"]))
            if key in seen:
                continue
            seen.add(key)
            first, second = (a, b) if sa <= sb else (b, a)
            # 両方とも「体を運ぶ」予定なら物理的に無理。Zoom 等は移動が要らない
            both_onsite = _is_onsite(first.get("location", "")) and _is_onsite(second.get("location", ""))
            out.append({
                "date": sa[:10],
                "id": first.get("id"), "title": first.get("title"),
                "start_iso": first.get("start_iso"), "end_iso": first.get("end_iso"),
                "location": first.get("location", ""),
                "other_id": second.get("id"), "other_title": second.get("title"),
                "other_start_iso": second.get("start_iso"), "other_end_iso": second.get("end_iso"),
                "other_location": second.get("location", ""),
                "both_onsite": both_onsite,
                "note": (
                    f"{sa[:10]} {(first.get('start_iso') or '')[11:16]}-{(first.get('end_iso') or '')[11:16]}"
                    f"「{first.get('title')}」と "
                    f"{(second.get('start_iso') or '')[11:16]}-{(second.get('end_iso') or '')[11:16]}"
                    f"「{second.get('title')}」が重なっています"
                    + ("。どちらも場所が指定されていて移動が要ります" if both_onsite else "")
                ),
            })
    out.sort(key=lambda x: x.get("start_iso", ""))
    return out


@router.get("/guard/scan")
def scan(days: int = Query(10, ge=1, le=30)):
    now = now_jst()
    today = now.strftime("%Y-%m-%d")
    tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    end = (now + timedelta(days=days + 1)).strftime("%Y-%m-%d")

    try:
        from gcal import list_events_range, is_configured, IMPORTANT_EVENT_TYPES
        if not is_configured():
            return {"configured": False, "must_not_miss": [], "date_suspects": [], "reminder_gaps": [], "overlaps": []}
        events = list_events_range(today, end)
    except Exception as e:
        return {"configured": False, "error": str(e), "must_not_miss": [], "date_suspects": [], "reminder_gaps": [], "overlaps": []}

    must_not_miss: list[dict] = []
    date_suspects: list[dict] = []
    reminder_gaps: list[dict] = []
    gap_seen: set[str] = set()  # (title, date) で多カレンダー重複を畳む

    for ev in events:
        title = ev.get("title", "")
        start_iso = ev.get("start_iso", "")
        etype = ev.get("event_type", "default")
        date_part = start_iso[:10]
        important = etype in IMPORTANT_EVENT_TYPES
        period = _is_multiday_period(ev)  # 夏季休業・受理期間などの「期間」は予定でないので対象外

        # 1. 日付ズレ疑い: タイトルの曜日 vs 実日付の曜日
        #    ※タイトルのみ見る (description には別日付の曜日が混ざり誤検知するため)
        wd_text = _weekday_in_text(title)
        if wd_text is not None and len(date_part) == 10 and not period:
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

        # 3. 通知欠落: 重要予定なのに前日通知なし (期間ものは除外・多カレンダー重複は畳む)
        if important and not period and not _has_day_before(ev.get("reminders", {})):
            gk = f"{title}::{date_part}"
            if gk not in gap_seen:
                gap_seen.add(gk)
                reminder_gaps.append({
                    "id": ev.get("id"), "slot": ev.get("slot"), "calendar_id": ev.get("calendar_id"),
                    "title": title, "start_iso": start_iso, "event_type": etype,
                })

    # 4. カレンダー間の日付食い違い (日程変更が片方だけ反映されていない)
    date_suspects.extend(_cross_calendar_conflicts(events))

    # 5. 同じ時間帯の重なり (当日になって気づくと詰む)
    overlaps = _overlaps(events)

    must_not_miss.sort(key=lambda x: x.get("start_iso", ""))
    reminder_gaps.sort(key=lambda x: x.get("start_iso", ""))
    date_suspects.sort(key=lambda x: x.get("start_iso", ""))
    return {
        "configured": True,
        "days": days,
        "must_not_miss": must_not_miss,
        "date_suspects": date_suspects,
        "reminder_gaps": reminder_gaps,
        "overlaps": overlaps,
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
