"""
Apple Health の取り込み口を増やす — iPhone 側の設定を短くするための追加ルート。

health_intake.py の POST /health-data は JSON 本文が要るぶん、
ショートカット App での組み立てが長くなる。ここでは 2 つ足す:

1. GET  /health-data/quick        URL に値を並べるだけ (2 アクションで済む)
2. POST /health-data/auto-export  Health Auto Export アプリの JSON をそのまま受ける

保存先・スキーマは health_intake と同じ (health_data.jsonl / 日付ごと latest-wins)。
"""

from __future__ import annotations

from fastapi import APIRouter

from data_manager import append_jsonl, timestamp_jst
from routers.health_intake import HEALTH_FILE, HealthIn, post_health

router = APIRouter()


@router.get("/health-data/quick")
def post_health_quick(
    sleep_hours: float | None = None,
    sleep_minutes: float | None = None,
    sleep_seconds: float | None = None,
    steps: int | None = None,
    resting_hr: int | None = None,
    hrv_ms: float | None = None,
    workout_minutes: int | None = None,
    energy_self: int | None = None,
    date: str = "",
):
    """ショートカットを短くするための GET 版。

    POST + ヘッダ + JSON 本文の組み立ては iPhone 上での設定が長い。
    URL に値を並べるだけで書き込めるようにして、ショートカット側を
    「ヘルスケアサンプルを検索」→「統計を計算(合計)」→「URL の内容を取得」の
    3 アクションで済ませる。GET で書き込むのは行儀が悪いが、個人用途なので
    手数を減らす方を取る。

    睡眠は「ヘルスサンプルを検索」が秒で返す。ショートカット側に計算
    アクションを足させないよう、秒・分のまま受けてこちらで時間に直す。
    """
    if sleep_hours is None:
        if sleep_seconds is not None:
            sleep_hours = round(sleep_seconds / 3600.0, 2)
        elif sleep_minutes is not None:
            sleep_hours = round(sleep_minutes / 60.0, 2)

    return post_health(
        HealthIn(
            date=date,
            sleep_hours=sleep_hours,
            steps=steps,
            resting_hr=resting_hr,
            hrv_ms=hrv_ms,
            workout_minutes=workout_minutes,
            energy_self=energy_self,
            note="shortcut",
        )
    )


def _day_of(raw: str) -> str:
    """'2026-01-21 14:15:00 +0000' でも '2026-01-21' でも日付部分だけ返す。"""
    return (raw or "").strip()[:10]


def _as_hours(v: float) -> float:
    """睡眠は分で来ることが多い。24 を超えたら分とみなして時間に直す。"""
    return round(v / 60.0, 2) if v > 24 else round(v, 2)


@router.post("/health-data/auto-export")
def post_auto_export(payload: dict):
    """Health Auto Export アプリの JSON をそのまま受ける。

    アプリ側で送信先 URL を 1 度入れるだけで済むように、向こうの形
    ({"data": {"metrics": [{name, units, data: [...]}, ...]}}) を
    こちらの 1 日 1 行に畳んで保存する。ショートカットを作らない場合の入口。
    """
    metrics = ((payload or {}).get("data") or {}).get("metrics") or []
    acc: dict[str, dict] = {}  # date -> 集計中の値

    for m in metrics:
        name = (m.get("name") or "").strip().lower()
        for row in m.get("data") or []:
            if not isinstance(row, dict):
                continue
            day = _day_of(row.get("date", ""))
            if not day:
                continue
            s = acc.setdefault(day, {})
            try:
                if name == "step count":
                    qty = row.get("qty")
                    if qty is not None:
                        s["steps"] = int(s.get("steps", 0) + float(qty))
                elif name == "sleep analysis":
                    v = row.get("asleep") or row.get("totalSleep")
                    if v is not None:
                        s["sleep_hours"] = _as_hours(float(v))
                elif name == "resting heart rate":
                    v = row.get("qty", row.get("Avg"))
                    if v is not None:
                        s["resting_hr"] = int(round(float(v)))
                elif name in ("heart rate variability", "heart rate variability sdnn"):
                    v = row.get("qty", row.get("Avg"))
                    if v is not None:
                        s["hrv_ms"] = round(float(v), 1)
                elif name in ("apple exercise time", "apple move time"):
                    qty = row.get("qty")
                    if qty is not None:
                        s["workout_minutes"] = int(s.get("workout_minutes", 0) + float(qty))
            except (TypeError, ValueError):
                # 想定外の型が来ても、その 1 行を捨てるだけにする
                continue

    saved = []
    for day, vals in sorted(acc.items()):
        if not vals:
            continue
        entry = HealthIn(date=day, **vals).model_dump()
        entry["date"] = day
        entry["note"] = "auto-export"
        entry["received_at"] = timestamp_jst()
        append_jsonl(HEALTH_FILE, entry)
        saved.append(day)

    return {"ok": True, "saved_days": saved, "count": len(saved)}
