"""
Completion log — mark today's calendar events / backlog tasks as done from Daily Brief.

Storage: append-only JSONL at data/completions.jsonl, tombstoned with _deleted entries.
Each completion ties to a (kind, ref_id, date) tuple so re-checking the same event the
same day is idempotent and unchecking is one DELETE call.

保育園の送迎のような「基本は毎回やる予定」は、毎日チェックを付けさせても続かない。
定例として登録した繰り返し予定は開始時刻を過ぎたら自動で済みにし (POST /completions/auto-fill)、
違った日だけ status=skipped / changed と理由・実際の時刻を記録する。
"""

from __future__ import annotations

from datetime import date as date_cls
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data_manager import (
    DATA_DIR,
    append_jsonl,
    init_jsonl,
    read_jsonl,
    now_jst,
    timestamp_jst,
)

from routers.work_log import demote_completion, promote_completion

router = APIRouter()

COMPLETIONS_FILE = DATA_DIR / "completions.jsonl"
init_jsonl(COMPLETIONS_FILE, "completion", "Daily Brief check-off log")

Kind = Literal["calendar", "backlog"]


Status = Literal["done", "skipped", "changed"]


class CompletionIn(BaseModel):
    kind: Kind = "calendar"
    ref_id: str
    title: str = ""
    date: str = ""  # YYYY-MM-DD; defaults to today JST
    category: str = ""  # optional, copied from backlog/event
    note: str = ""
    status: Status = "done"     # done=予定通り / skipped=やらなかった / changed=形を変えてやった
    actual_time: str = ""       # HH:MM 実際にやった時刻 (予定とずれた日だけ入れる)
    source: str = ""            # "" = 手でチェック, "routine-auto" = 定例の自動チェック


def _today_jst() -> str:
    return now_jst().strftime("%Y-%m-%d")


def _work_ref(kind: str, ref_id: str) -> str:
    """実績台帳側の参照キー。calendar と backlog で id が衝突しないよう種別を前置する。"""
    return f"{kind}:{ref_id}" if ref_id else ""


def _outcome_text(note: str, actual_time: str, status: str) -> str:
    """実績台帳に残す一言。予定とずれた日は、ずれた事実そのものが記録になる。"""
    parts = []
    if actual_time:
        parts.append(f"実施 {actual_time}")
    if status == "changed":
        parts.append("予定から変更")
    if note:
        parts.append(note)
    return " / ".join(parts)


def _series_key(ref_id: str) -> str:
    """繰り返し予定の系列キー。Google の id は 'xxxx_20260817T223000Z' の形で、
    前半が系列、後半がその日の回。系列で登録できないと毎回登録し直しになる。"""
    return (ref_id or "").split("_", 1)[0]


def _deleted_keys() -> set[tuple[str, str, str]]:
    """一度チェックを外した (kind, ref_id, date)。自動チェックが蒸し返さないための記憶。"""
    out: set[tuple[str, str, str]] = set()
    for entry in read_jsonl(COMPLETIONS_FILE):
        key = (entry.get("kind", "calendar"), entry.get("ref_id", ""), entry.get("date", ""))
        if not key[1] or not key[2]:
            continue
        if entry.get("_deleted"):
            out.add(key)
        else:
            out.discard(key)
    return out


def _current_state() -> dict[tuple[str, str, str], dict]:
    """Replay the JSONL into a map keyed by (kind, ref_id, date).

    Tombstones (`_deleted: true`) remove the matching key.
    """
    state: dict[tuple[str, str, str], dict] = {}
    for entry in read_jsonl(COMPLETIONS_FILE):
        kind = entry.get("kind", "calendar")
        ref_id = entry.get("ref_id", "")
        date = entry.get("date", "")
        if not ref_id or not date:
            continue
        key = (kind, ref_id, date)
        if entry.get("_deleted"):
            state.pop(key, None)
        else:
            state[key] = entry
    return state


@router.get("/completions")
def list_completions(
    date: str = Query("", description="YYYY-MM-DD, defaults to today JST"),
    kind: str = Query("", description="optional filter: calendar / backlog"),
):
    target_date = date or _today_jst()
    state = _current_state()
    items = [
        v for (k, _ref, d), v in state.items()
        if d == target_date and (not kind or k == kind)
    ]
    items.sort(key=lambda x: x.get("completed_at", ""))
    return {"date": target_date, "items": items}


@router.post("/completions")
def add_completion(payload: CompletionIn):
    target_date = payload.date or _today_jst()
    # sanity-check date format
    try:
        date_cls.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    if not payload.ref_id:
        raise HTTPException(status_code=400, detail="ref_id required")

    entry = {
        "kind": payload.kind,
        "ref_id": payload.ref_id,
        "title": payload.title,
        "date": target_date,
        "category": payload.category,
        "note": payload.note,
        "status": payload.status,
        "actual_time": payload.actual_time,
        "source": payload.source,
        "completed_at": timestamp_jst(),
    }
    append_jsonl(COMPLETIONS_FILE, entry)

    # チェックした事実を実績台帳へ残す。ここを繋いでいなかったので、
    # 予定を消化してもあとから「やったかどうか」を確かめられなかった。
    # やらなかった日 (skipped) は実績ではないので台帳には積まず、記録だけ残す。
    if payload.status == "skipped":
        demote_completion(_work_ref(payload.kind, payload.ref_id), target_date)
        return {**entry, "work_logged": False}

    promoted = promote_completion(
        title=payload.title,
        date=target_date,
        category=payload.category,
        outcome=_outcome_text(payload.note, payload.actual_time, payload.status),
        ref_id=_work_ref(payload.kind, payload.ref_id),
    )
    return {**entry, "work_logged": bool(promoted.get("created"))}


@router.delete("/completions")
def remove_completion(
    ref_id: str = Query(..., description="event/backlog ID"),
    kind: str = Query("calendar"),
    date: str = Query("", description="YYYY-MM-DD, defaults to today JST"),
):
    target_date = date or _today_jst()
    state = _current_state()
    key = (kind, ref_id, target_date)
    if key not in state:
        return {"ok": True, "removed": False}
    tombstone = {
        "kind": kind,
        "ref_id": ref_id,
        "date": target_date,
        "_deleted": True,
        "deleted_at": timestamp_jst(),
    }
    append_jsonl(COMPLETIONS_FILE, tombstone)
    demote_completion(_work_ref(kind, ref_id), target_date)
    return {"ok": True, "removed": True}


# ─── 定例 (毎回やる繰り返し予定) ───────────────────────────────────────────────
#
# 保育園の送迎のように「基本は必ずやる」予定は、毎日チェックを付ける手間の方が
# 続かない理由になる。系列ごとに一度だけ「定例」と登録しておけば、開始時刻を
# 過ぎた分は自動で済みになり、違った日だけ手を入れれば済む。

ROUTINES_FILE = DATA_DIR / "completion_routines.jsonl"
init_jsonl(ROUTINES_FILE, "completion_routine", "毎回やる繰り返し予定 (自動チェック対象)")


class RoutineIn(BaseModel):
    series_key: str          # 繰り返し予定の系列 id (回ごとの suffix を落としたもの)
    title: str = ""
    auto_done: bool = True   # False にすると登録は残しつつ自動チェックだけ止める


def _routine_state() -> dict[str, dict]:
    state: dict[str, dict] = {}
    for entry in read_jsonl(ROUTINES_FILE):
        key = entry.get("series_key", "")
        if not key:
            continue
        if entry.get("_deleted"):
            state.pop(key, None)
        else:
            state[key] = entry
    return state


@router.get("/completions/routines")
def list_routines():
    items = sorted(_routine_state().values(), key=lambda r: r.get("title", ""))
    return {"items": items, "count": len(items)}


@router.post("/completions/routines")
def add_routine(payload: RoutineIn):
    key = _series_key(payload.series_key)
    if not key:
        raise HTTPException(status_code=400, detail="series_key required")
    entry = {
        "series_key": key,
        "title": payload.title,
        "auto_done": payload.auto_done,
        "updated_at": timestamp_jst(),
    }
    append_jsonl(ROUTINES_FILE, entry)
    return entry


@router.delete("/completions/routines")
def remove_routine(series_key: str = Query(...)):
    key = _series_key(series_key)
    if key not in _routine_state():
        return {"ok": True, "removed": False}
    append_jsonl(ROUTINES_FILE, {"series_key": key, "_deleted": True, "deleted_at": timestamp_jst()})
    return {"ok": True, "removed": True}


class AutoFillEvent(BaseModel):
    id: str
    title: str = ""
    start: str = ""     # ISO8601。終日予定は "YYYY-MM-DD"


class AutoFillIn(BaseModel):
    date: str = ""
    events: list[AutoFillEvent] = []


def _has_started(start: str, target_date: str) -> bool:
    """開始時刻を過ぎたか。まだ来ていない予定を先に済みにはしない。"""
    now = now_jst()
    today = now.strftime("%Y-%m-%d")
    if target_date < today:
        return True
    if target_date > today:
        return False
    if not start or len(start) <= 10:   # 終日予定はその日のうちに済み扱い
        return True
    try:
        from datetime import datetime as _dt
        return _dt.fromisoformat(start.replace("Z", "+00:00")) <= now
    except ValueError:
        return True


@router.post("/completions/auto-fill")
def auto_fill(payload: AutoFillIn):
    """定例に登録済みの予定を、開始時刻を過ぎた分だけ自動で済みにする。

    暴走しないための縛り:
    - 未来の日付は触らない。今日なら開始時刻を過ぎたものだけ
    - すでに記録がある回は作らない (再実行しても増えない)
    - 一度チェックを外した回は蒸し返さない
    """
    target_date = payload.date or _today_jst()
    try:
        date_cls.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    if target_date > _today_jst():
        return {"date": target_date, "created": [], "count": 0}

    routines = _routine_state()
    if not routines:
        return {"date": target_date, "created": [], "count": 0}

    state = _current_state()
    dropped = _deleted_keys()
    created: list[dict] = []

    for ev in payload.events:
        if not ev.id:
            continue
        routine = routines.get(_series_key(ev.id))
        if not routine or not routine.get("auto_done", True):
            continue
        key = ("calendar", ev.id, target_date)
        if key in state or key in dropped:
            continue
        if not _has_started(ev.start, target_date):
            continue
        entry = {
            "kind": "calendar",
            "ref_id": ev.id,
            "title": ev.title or routine.get("title", ""),
            "date": target_date,
            "category": "",
            "note": "",
            "status": "done",
            "actual_time": "",
            "source": "routine-auto",
            "completed_at": timestamp_jst(),
        }
        append_jsonl(COMPLETIONS_FILE, entry)
        promote_completion(
            title=entry["title"],
            date=target_date,
            ref_id=_work_ref("calendar", ev.id),
        )
        created.append(entry)

    return {"date": target_date, "created": created, "count": len(created)}
