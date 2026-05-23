"""
Apple Health 連携 — iOS Shortcut が POST する JSON を受け取り、
睡眠 / 心拍 / 歩数を保存し、Daily Brief のトーン調整に使う。

Shortcut のサンプル body:
{
  "date": "2026-05-24",
  "sleep_hours": 6.2,
  "steps": 8200,
  "resting_hr": 62,
  "hrv_ms": 45,
  "workout_minutes": 0,
  "energy_self": 3
}

energy_self は本人入力（1〜5）。Shortcut の prompt step で取る。
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from data_manager import (
    DATA_DIR,
    append_jsonl,
    init_jsonl,
    read_jsonl,
    now_jst,
    timestamp_jst,
)

router = APIRouter()

HEALTH_FILE = DATA_DIR / "health_data.jsonl"
init_jsonl(HEALTH_FILE, "health_data", "Apple Health + self report")


class HealthIn(BaseModel):
    date: str = ""  # YYYY-MM-DD; defaults to today JST
    sleep_hours: float | None = None
    steps: int | None = None
    resting_hr: int | None = None
    hrv_ms: float | None = None
    workout_minutes: int | None = None
    energy_self: int | None = None  # 1〜5
    note: str = ""


def _today() -> str:
    return now_jst().strftime("%Y-%m-%d")


def _current_state() -> dict[str, dict]:
    """date -> latest entry"""
    state: dict[str, dict] = {}
    for e in read_jsonl(HEALTH_FILE):
        d = e.get("date", "")
        if not d:
            continue
        state[d] = e
    return state


@router.post("/health-data")
def post_health(payload: HealthIn):
    target = payload.date or _today()
    entry = payload.model_dump()
    entry["date"] = target
    entry["received_at"] = timestamp_jst()
    append_jsonl(HEALTH_FILE, entry)
    return entry


@router.get("/health-data/today")
def health_today():
    state = _current_state()
    return state.get(_today(), {"date": _today(), "empty": True})


@router.get("/health-data/recent")
def health_recent(days: int = Query(7, ge=1, le=60)):
    from datetime import timedelta
    cutoff = (now_jst().date() - timedelta(days=days - 1)).isoformat()
    state = _current_state()
    out = [v for d, v in state.items() if d >= cutoff]
    out.sort(key=lambda x: x.get("date", ""))
    return {"days": days, "items": out}


@router.get("/health-data/state-hint")
def state_hint():
    """Brief / coach に注入する一行ヒント。AI のトーン調整用。"""
    today = _current_state().get(_today())
    if not today:
        return {"hint": "", "energy_band": "unknown"}
    parts = []
    band = "neutral"
    sleep = today.get("sleep_hours")
    if sleep is not None:
        if sleep < 5.0:
            parts.append(f"睡眠 {sleep:.1f}h (短い)")
            band = "low"
        elif sleep < 6.5:
            parts.append(f"睡眠 {sleep:.1f}h (やや短)")
            if band == "neutral":
                band = "low"
        else:
            parts.append(f"睡眠 {sleep:.1f}h")
    energy = today.get("energy_self")
    if energy:
        parts.append(f"自己エネルギー {energy}/5")
        if energy <= 2:
            band = "low"
        elif energy >= 4 and band == "neutral":
            band = "high"
    steps = today.get("steps")
    if steps is not None:
        parts.append(f"歩数 {steps}")
    hint = " ・ ".join(parts) if parts else ""
    return {"hint": hint, "energy_band": band}
