"""
Routines — Cowork 風の定期/オンデマンド自動タスク。

「タスクを一度記述 → cadence 指定 → 自動で回る」を Koach OS ネイティブで実現する。
3 種類:
- ai      : 自由文タスクを dispatch_auto の engine 自動選択で実行 (Koach OS の手が届く範囲で自走)
- builtin : 既存ジョブ (daily-brief / evening-brief / weekly-review / patterns / email-scan) を呼ぶ
- cowork  : Cowork 貼り付け用のタスク指示書を文脈付きで用意 (本物の Cowork に渡す前提。クラウドで自走させない)

発火: GitHub Actions cron が 30 分毎に POST /api/routines/run-due (X-Cron-Token) を叩く。
      エンドポイント側で「今 due なルーティン」を JST + last_run から判定して実行する。
保存: routines.jsonl (定義) / routine_runs.jsonl (実行履歴フィード)。append-only, latest-wins, tombstone。
既存ファイルには非干渉。
"""

from __future__ import annotations

import json
import os
import urllib.request
from datetime import datetime as _dt

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from data_manager import (
    DATA_DIR,
    append_jsonl,
    read_jsonl,
    generate_id,
    now_jst,
    timestamp_jst,
)
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

ROUTINES_FILE = DATA_DIR / "routines.jsonl"
RUNS_FILE = DATA_DIR / "routine_runs.jsonl"

CADENCES = ["manual", "hourly", "daily", "weekdays", "weekly"]
KINDS = ["ai", "builtin", "cowork"]
BUILTINS = [
    {"ref": "daily-brief", "label": "朝のブリーフ生成"},
    {"ref": "evening-brief", "label": "夜の振り返り生成"},
    {"ref": "weekly-review", "label": "週次レビュー生成"},
    {"ref": "patterns", "label": "行動パターン分析 (再生成)"},
    {"ref": "email-scan", "label": "対応待ちメール スキャン"},
]


# ─── store ───
def _materialize() -> dict[str, dict]:
    state: dict[str, dict] = {}
    for e in read_jsonl(ROUTINES_FILE):
        rid = e.get("id")
        if not rid:
            continue
        if e.get("_deleted"):
            state.pop(rid, None)
            continue
        state[rid] = e
    return state


def _check_token(token: str | None) -> None:
    expected = os.environ.get("CRON_TOKEN", "")
    if not expected:
        raise HTTPException(503, "CRON_TOKEN not configured")
    if token != expected:
        raise HTTPException(401, "invalid cron token")


def _send_email(subject: str, text: str) -> bool:
    api_key = os.environ.get("RESEND_API_KEY", "")
    to_email = os.environ.get("NOTIFY_EMAIL", "")
    from_email = os.environ.get("NOTIFY_FROM", "Koach OS <onboarding@resend.dev>")
    if not api_key or not to_email:
        return False
    payload = json.dumps(
        {"from": from_email, "to": [to_email], "subject": subject, "text": text}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "koach-os/1.0 (+https://koach-os.vercel.app)",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15):
            return True
    except Exception:
        return False


# ─── execution ───
def _extract_text(d) -> str:
    if isinstance(d, str):
        return d
    if isinstance(d, dict):
        for k in ("report", "review", "ai_brief", "summary", "result", "text", "answer"):
            v = d.get(k)
            if isinstance(v, str) and v.strip():
                return v
        return json.dumps(d, ensure_ascii=False)[:2000]
    return str(d)


def _run_ai(task: str, engine_req: str) -> tuple[str, str]:
    from routers.dispatch_auto import _route, EXEC_SYSTEM
    if engine_req == "auto" or engine_req not in DEFAULT_MODELS:
        eng, _reason = _route(task, None)
    else:
        eng = engine_req
    out = call_ai(
        messages=[{"role": "user", "content": task}],
        system=EXEC_SYSTEM,
        engine=eng,
        model=DEFAULT_MODELS[eng],
        max_tokens=1500,
    )
    return out, eng


def _run_builtin(ref: str, engine: str) -> tuple[str, str]:
    eng = "claude" if engine == "auto" else engine
    if ref == "daily-brief":
        from routers.daily_brief import daily_brief as fn
        d = fn(engine=eng, model=None, force=True)
        return _extract_text(d), d.get("engine_used", eng)
    if ref == "evening-brief":
        from routers.evening_brief import evening_brief as fn
        d = fn(engine=eng)
        return _extract_text(d), d.get("engine_used", eng)
    if ref == "weekly-review":
        from routers.weekly_review import weekly_review as fn
        d = fn(engine=eng)
        return _extract_text(d), d.get("engine_used", eng)
    if ref == "patterns":
        from routers.patterns import _generate as fn
        d = fn(engine=eng)
        return _extract_text(d), d.get("engine_used", eng)
    if ref == "email-scan":
        from routers.email_watch import _do_scan, ScanReq
        d = _do_scan(ScanReq())
        txt = (
            f"スキャン {d.get('scanned')} 件 / 新規分類 {d.get('new_classified')} 件 / "
            f"追加 {d.get('added_followups')} 件 / 合計追跡 {d.get('total_tracked')} 件"
        )
        return txt, eng
    raise ValueError(f"unknown builtin: {ref}")


def _build_cowork_brief(routine: dict) -> str:
    ctx: list[str] = []
    # 今日の予定
    try:
        from gcal import is_configured, get_events
        if is_configured():
            evs = get_events(days_ahead=0) or []
            if evs:
                ctx.append("今日の予定:\n" + "\n".join(f"- {e.get('summary','')}" for e in evs[:10]))
            else:
                ctx.append("今日の予定: なし")
    except Exception:
        pass
    # 対応待ちメール件数
    try:
        from routers.email_watch import _load, _is_pending
        today = now_jst().strftime("%Y-%m-%d")
        items = (_load().get("items", {}) or {}).values()
        pending = [it for it in items if _is_pending(it, today)]
        ctx.append(f"対応待ちメール: {len(pending)} 件")
    except Exception:
        pass
    # 直近の実績ログ
    try:
        from routers.work_log import _materialize as _wl
        recent = sorted(_wl().values(), key=lambda w: w.get("date", ""), reverse=True)[:5]
        if recent:
            ctx.append("直近の実績:\n" + "\n".join(f"- {w.get('date','')} {w.get('title','')}" for w in recent))
    except Exception:
        pass

    ctx_text = "\n\n".join(ctx) if ctx else "(文脈データなし)"
    return f"""# Cowork タスク: {routine.get('name','')}

## やってほしいこと
{routine.get('task','')}

## 今の文脈 (Koach OS より自動収集)
{ctx_text}

## 進め方
- 上記タスクを最後まで完了してください
- 必要ならローカルのファイル/アプリも使ってください
- 完了したら要点だけ報告してください

（この指示書は Koach OS が用意しました。Claude / Cowork を開いて、そのまま渡して実行してください）
"""


def _execute(routine: dict, trigger: str) -> dict:
    kind = routine.get("kind", "ai")
    engine_req = routine.get("engine", "auto")
    rec: dict = {
        "id": generate_id("run"),
        "routine_id": routine.get("id", ""),
        "routine_name": routine.get("name", ""),
        "kind": kind,
        "trigger": trigger,
        "started_at": timestamp_jst(),
    }
    try:
        if kind == "builtin":
            text, eng = _run_builtin(routine.get("builtin_ref", ""), engine_req)
            rec.update(status="ok", engine_used=eng, result_text=text[:4000])
        elif kind == "cowork":
            brief = _build_cowork_brief(routine)
            rec.update(status="prepared", engine_used="(cowork handoff)", result_text=brief[:6000])
        else:
            text, eng = _run_ai(routine.get("task", ""), engine_req)
            rec.update(status="ok", engine_used=eng, result_text=text[:4000])
    except Exception as e:
        rec.update(status="error", error=str(e)[:600])
    rec["finished_at"] = timestamp_jst()
    append_jsonl(RUNS_FILE, rec)

    # last_run / last_status を更新 (定義を上書き append)
    updated = {**routine, "last_run": rec["finished_at"], "last_status": rec.get("status"), "updated_at": timestamp_jst()}
    append_jsonl(ROUTINES_FILE, updated)

    # 配信
    if routine.get("delivery") == "email" and rec.get("status") in ("ok", "prepared"):
        _send_email(f"🤖 {routine.get('name','routine')} ({rec.get('status')})", rec.get("result_text", ""))
    return rec


# ─── cadence ───
def _is_due(r: dict, now) -> bool:
    if not r.get("enabled", True):
        return False
    cad = r.get("cadence", "manual")
    if cad == "manual":
        return False
    last = r.get("last_run") or ""
    today = now.strftime("%Y-%m-%d")
    at_hour = int(r.get("at_hour", 8))
    if cad == "hourly":
        if not last:
            return True
        try:
            return (now - _dt.fromisoformat(last)).total_seconds() >= 3300  # ~55 分
        except Exception:
            return True
    ran_today = last[:10] == today
    if cad == "daily":
        return (not ran_today) and now.hour >= at_hour
    if cad == "weekdays":
        return now.weekday() < 5 and (not ran_today) and now.hour >= at_hour
    if cad == "weekly":
        return now.weekday() == int(r.get("weekday", 0)) and (not ran_today) and now.hour >= at_hour
    return False


# ─── models ───
class RoutineCreate(BaseModel):
    name: str
    kind: str = "ai"
    task: str = ""
    builtin_ref: str = ""
    cadence: str = "daily"
    at_hour: int = 8
    weekday: int = 0
    engine: str = "auto"
    delivery: str = "inapp"
    enabled: bool = True


class RoutineUpdate(BaseModel):
    name: str | None = None
    kind: str | None = None
    task: str | None = None
    builtin_ref: str | None = None
    cadence: str | None = None
    at_hour: int | None = None
    weekday: int | None = None
    engine: str | None = None
    delivery: str | None = None
    enabled: bool | None = None


# ─── endpoints ───
@router.get("/routines/meta")
def routines_meta():
    return {"cadences": CADENCES, "kinds": KINDS, "builtins": BUILTINS, "engines": ["auto", *DEFAULT_MODELS.keys()]}


@router.get("/routines")
def list_routines():
    items = list(_materialize().values())
    items.sort(key=lambda r: (not r.get("enabled", True), r.get("name", "")))
    return {"routines": items, "count": len(items)}


@router.post("/routines")
def create_routine(req: RoutineCreate):
    if not req.name.strip():
        raise HTTPException(400, "name required")
    if req.kind not in KINDS:
        raise HTTPException(400, f"kind must be one of {KINDS}")
    if req.cadence not in CADENCES:
        raise HTTPException(400, f"cadence must be one of {CADENCES}")
    if req.kind == "builtin" and req.builtin_ref not in {b["ref"] for b in BUILTINS}:
        raise HTTPException(400, "invalid builtin_ref")
    if req.kind in ("ai", "cowork") and not req.task.strip():
        raise HTTPException(400, "task required for ai/cowork routine")
    now = timestamp_jst()
    entry = {
        "id": generate_id("routine"),
        "name": req.name.strip(),
        "kind": req.kind,
        "task": req.task.strip(),
        "builtin_ref": req.builtin_ref,
        "cadence": req.cadence,
        "at_hour": req.at_hour,
        "weekday": req.weekday,
        "engine": req.engine,
        "delivery": req.delivery,
        "enabled": req.enabled,
        "last_run": None,
        "last_status": None,
        "created_at": now,
        "updated_at": now,
    }
    append_jsonl(ROUTINES_FILE, entry)
    return entry


@router.patch("/routines/{routine_id}")
def update_routine(routine_id: str, req: RoutineUpdate):
    current = _materialize().get(routine_id)
    if not current:
        raise HTTPException(404, "routine not found")
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    new = {**current, **updates, "updated_at": timestamp_jst()}
    append_jsonl(ROUTINES_FILE, new)
    return new


@router.delete("/routines/{routine_id}")
def delete_routine(routine_id: str):
    if not _materialize().get(routine_id):
        raise HTTPException(404, "routine not found")
    append_jsonl(ROUTINES_FILE, {"id": routine_id, "_deleted": True, "deleted_at": timestamp_jst()})
    return {"deleted": True, "id": routine_id}


@router.post("/routines/{routine_id}/run")
def run_now(routine_id: str):
    routine = _materialize().get(routine_id)
    if not routine:
        raise HTTPException(404, "routine not found")
    rec = _execute(routine, trigger="manual")
    return rec


@router.get("/routines/runs")
def list_runs(limit: int = 30):
    runs = read_jsonl(RUNS_FILE)
    runs.sort(key=lambda r: r.get("started_at", ""), reverse=True)
    return {"runs": runs[:limit], "count": len(runs)}


@router.post("/routines/run-due")
def run_due(x_cron_token: str | None = Header(None, alias="X-Cron-Token")):
    """GitHub Actions cron が定期的に叩く。今 due なルーティンだけ実行。"""
    _check_token(x_cron_token)
    now = now_jst()
    ran = []
    for r in _materialize().values():
        if _is_due(r, now):
            rec = _execute(r, trigger="cron")
            ran.append({"name": r.get("name"), "status": rec.get("status")})
    return {"ok": True, "ran": ran, "count": len(ran), "checked_at": now.isoformat()}
