"""
GET/POST/PATCH/DELETE /api/tasks — Task management.

Tasks are stored append-only in tasks.jsonl with the latest entry per task ID
representing the current state. (Like decisions.jsonl pattern.)
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from data_manager import (
    append_jsonl,
    read_jsonl,
    TASKS_FILE,
    generate_id,
    timestamp_jst,
    now_jst,
)
from gcal import is_configured as gcal_is_configured, create_event as gcal_create_event
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

VALID_STATUS = {"todo", "in_progress", "done"}
VALID_PRIORITY = {"high", "medium", "low"}


# ─── Helpers ────────────────────────────────────────────


def _materialize_state() -> dict[str, dict]:
    """Read append-only log and reduce to current state per task id.

    Each log entry is a full task dict (or {id, _deleted: True} for deletions).
    """
    state: dict[str, dict] = {}
    for entry in read_jsonl(TASKS_FILE):
        tid = entry.get("id")
        if not tid:
            continue
        if entry.get("_deleted"):
            state.pop(tid, None)
            continue
        state[tid] = entry
    return state


def _get(task_id: str) -> dict | None:
    state = _materialize_state()
    return state.get(task_id)


def _save(task: dict) -> None:
    """Append the new task state to log."""
    append_jsonl(TASKS_FILE, task)


# ─── Models ─────────────────────────────────────────────


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    status: str = "todo"
    priority: str = "medium"
    due_date: str | None = None        # YYYY-MM-DD
    due_time: str | None = None        # HH:MM
    estimated_minutes: int | None = None
    category: str = "personal"


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: str | None = None
    priority: str | None = None
    due_date: str | None = None
    due_time: str | None = None
    estimated_minutes: int | None = None
    category: str | None = None


class TaskToCalendarRequest(BaseModel):
    event_type: str | None = None  # meeting/committee/deadline/default — auto if None


# ─── Endpoints ──────────────────────────────────────────


@router.get("/tasks")
def list_tasks(
    status: str | None = Query(None),
    category: str | None = Query(None),
):
    """List all tasks (latest state). Filter by status/category."""
    state = _materialize_state()
    tasks = list(state.values())

    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    if category:
        tasks = [t for t in tasks if t.get("category") == category]

    # Sort: due_date asc (None last), then priority high→low, then created_at asc
    priority_rank = {"high": 0, "medium": 1, "low": 2}
    tasks.sort(
        key=lambda t: (
            t.get("status") == "done",
            t.get("due_date") or "9999-12-31",
            priority_rank.get(t.get("priority", "medium"), 1),
            t.get("created_at", ""),
        )
    )
    return {"tasks": tasks, "count": len(tasks)}


@router.get("/tasks/today")
def todays_tasks():
    """Tasks due today or earlier (incl. overdue), and ones in progress."""
    state = _materialize_state()
    today = now_jst().strftime("%Y-%m-%d")
    today_or_earlier = []
    in_progress = []
    for t in state.values():
        if t.get("status") == "done":
            continue
        due = t.get("due_date")
        if due and due <= today:
            today_or_earlier.append(t)
        elif t.get("status") == "in_progress":
            in_progress.append(t)
    return {
        "due_today_or_overdue": today_or_earlier,
        "in_progress": in_progress,
    }


@router.post("/tasks")
def create_task(req: TaskCreate):
    """Create a new task."""
    if req.status not in VALID_STATUS:
        raise HTTPException(400, f"status must be one of {VALID_STATUS}")
    if req.priority not in VALID_PRIORITY:
        raise HTTPException(400, f"priority must be one of {VALID_PRIORITY}")

    now = timestamp_jst()
    task = {
        "id": generate_id("task"),
        "title": req.title,
        "description": req.description,
        "status": req.status,
        "priority": req.priority,
        "due_date": req.due_date,
        "due_time": req.due_time,
        "estimated_minutes": req.estimated_minutes,
        "category": req.category,
        "gcal_event_id": None,
        "created_at": now,
        "updated_at": now,
        "completed_at": None,
    }
    _save(task)
    return task


@router.patch("/tasks/{task_id}")
def update_task(task_id: str, req: TaskUpdate):
    """Update a task. Pass only the fields to change."""
    current = _get(task_id)
    if not current:
        raise HTTPException(404, "Task not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "status" in updates and updates["status"] not in VALID_STATUS:
        raise HTTPException(400, f"status must be one of {VALID_STATUS}")
    if "priority" in updates and updates["priority"] not in VALID_PRIORITY:
        raise HTTPException(400, f"priority must be one of {VALID_PRIORITY}")

    now = timestamp_jst()
    new = {**current, **updates, "updated_at": now}

    # Auto-set completed_at when status flips to done
    if updates.get("status") == "done" and not current.get("completed_at"):
        new["completed_at"] = now
    elif updates.get("status") and updates["status"] != "done":
        new["completed_at"] = None

    _save(new)
    return new


@router.delete("/tasks/{task_id}")
def delete_task(task_id: str):
    """Delete a task (soft-delete via append-only log)."""
    if not _get(task_id):
        raise HTTPException(404, "Task not found")
    _save({"id": task_id, "_deleted": True, "deleted_at": timestamp_jst()})
    return {"deleted": True, "id": task_id}


@router.post("/tasks/{task_id}/to-calendar")
def task_to_calendar(task_id: str, req: TaskToCalendarRequest):
    """Add this task to Google Calendar with type-aware reminder."""
    task = _get(task_id)
    if not task:
        raise HTTPException(404, "Task not found")
    if not gcal_is_configured():
        raise HTTPException(400, "Google Calendar not configured")

    due_date = task.get("due_date")
    if not due_date:
        raise HTTPException(400, "Task has no due_date — cannot add to calendar")

    due_time = task.get("due_time")
    estimated = task.get("estimated_minutes") or 60

    if due_time:
        # Timed event
        from datetime import datetime, timedelta
        from data_manager import JST

        start_dt = datetime.fromisoformat(f"{due_date}T{due_time}:00").replace(tzinfo=JST)
        end_dt = start_dt + timedelta(minutes=estimated)
        start_iso = start_dt.isoformat()
        end_iso = end_dt.isoformat()
    else:
        # All-day event
        start_iso = due_date
        end_iso = due_date

    try:
        event = gcal_create_event(
            title=task["title"],
            start_iso=start_iso,
            end_iso=end_iso,
            description=task.get("description", ""),
            location="",
            event_type=req.event_type,
        )
    except Exception as e:
        raise HTTPException(500, f"Calendar event creation failed: {e}")

    # Update task with gcal_event_id
    updated = {**task, "gcal_event_id": event.get("id"), "updated_at": timestamp_jst()}
    _save(updated)

    return {
        "task": updated,
        "event_id": event.get("id"),
        "html_link": event.get("htmlLink"),
        "event_type_used": event.get("_event_type_used", "default"),
    }


# ─── Auto-reschedule (schedule-manager から移植) ─────────────────────────

RESCHEDULE_SYSTEM = """あなたは大学教員 (志柿) のスケジュール最適化アシスタント。
1 つのタスクが変わったので、他の未完了タスクの締切・時刻の組み直し案を出す。

ルール:
- 優先順位: 家族 > 学生 > 研究 > プラットフォーム > 収益 > 個人成長
- 裁量労働制で時間は柔軟だが、締切 (deadline / 提出) は厳守
- 会議・授業は動かさない
- 締切が近いタスクは前倒し推奨
- 変更不要なら suggestions は空配列

出力 JSON (これのみ。Markdown 禁止):
{
  "suggestions": [
    {"task_id":"task_xxx","new_due_date":"YYYY-MM-DD","new_due_time":"HH:MM"|null,"reason":"理由"}
  ],
  "summary": "全体アドバイス 1〜2 文。です/ます調、抽象名詞『〜性』NG"
}"""


class RescheduleReq(BaseModel):
    changed_task_id: str
    action: str = "completed"   # completed | rescheduled | deleted | added
    engine: str = "gpt"


@router.post("/tasks/reschedule")
def reschedule(req: RescheduleReq):
    """1 タスクの変更を起点に、他タスクの組み直し案を AI に出させる (提案のみ)。"""
    state = _materialize_state()
    changed = state.get(req.changed_task_id)
    if not changed and req.action != "deleted":
        raise HTTPException(404, "changed task not found")

    pending = [t for t in state.values() if t.get("status") != "done"
               and t.get("id") != req.changed_task_id]
    if not pending:
        return {"suggestions": [], "summary": "未完了タスクが他にありません。"}

    today = now_jst().strftime("%Y-%m-%d")
    lines = "\n".join(
        f"- [{t['id']}] {t.get('title','')} | カテゴリ {t.get('category','other')} "
        f"| 優先度 {t.get('priority','medium')} | 期限 {t.get('due_date') or '未設定'} "
        f"{t.get('due_time') or ''} | 状態 {t.get('status','todo')} "
        f"| 見積 {t.get('estimated_minutes') or '?'}分"
        for t in pending
    )

    act_label = {"completed": "完了", "rescheduled": "日程変更",
                 "deleted": "削除", "added": "追加"}.get(req.action, req.action)
    changed_title = (changed or {}).get("title", "(削除済みタスク)")
    user = f"""今日: {today}

変更: タスク「{changed_title}」が{act_label}されました。

現在の未完了タスク:
{lines}

他タスクの組み直し案を JSON で出してください。"""

    engine = req.engine if req.engine in DEFAULT_MODELS else "gpt"
    try:
        raw = call_ai(
            messages=[{"role": "user", "content": user}],
            system=RESCHEDULE_SYSTEM,
            engine=engine,
            model=DEFAULT_MODELS[engine],
            max_tokens=1500,
        )
    except Exception as e:
        raise HTTPException(500, f"reschedule failed: {e}")

    import json as _json
    import re as _re
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = _re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = _re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = _json.loads(cleaned)
    except Exception:
        m = _re.search(r"\{.*\}", cleaned, _re.DOTALL)
        parsed = _json.loads(m.group(0)) if m else {"suggestions": [], "summary": ""}

    return {
        "suggestions": parsed.get("suggestions", []),
        "summary": parsed.get("summary", ""),
        "engine_used": engine,
    }


class RescheduleApplyReq(BaseModel):
    suggestions: list[dict] = []   # [{task_id, new_due_date, new_due_time}]


@router.post("/tasks/reschedule/apply")
def reschedule_apply(req: RescheduleApplyReq):
    """組み直し案を実タスクに反映 (due_date/due_time 更新)。"""
    applied = []
    for s in req.suggestions:
        tid = s.get("task_id")
        task = _get(tid) if tid else None
        if not task:
            continue
        new = {**task, "updated_at": timestamp_jst()}
        if s.get("new_due_date"):
            new["due_date"] = s["new_due_date"]
        if "new_due_time" in s:
            new["due_time"] = s.get("new_due_time")
        _save(new)
        applied.append(tid)
    return {"applied": applied, "count": len(applied)}
