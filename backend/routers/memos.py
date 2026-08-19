"""
GET/POST/PATCH/DELETE /api/memos — Sticky-note memos.

Append-only log; latest entry per id wins. Same pattern as tasks.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import (
    append_jsonl,
    read_jsonl,
    MEMOS_FILE,
    generate_id,
    timestamp_jst,
)

router = APIRouter()

VALID_COLORS = {"yellow", "blue", "green", "pink"}


def _materialize() -> dict[str, dict]:
    state: dict[str, dict] = {}
    for e in read_jsonl(MEMOS_FILE):
        mid = e.get("id")
        if not mid:
            continue
        if e.get("_deleted"):
            state.pop(mid, None)
            continue
        state[mid] = e
    return state


class MemoCreate(BaseModel):
    content: str
    color: str = "yellow"
    pinned: bool = False


class MemoUpdate(BaseModel):
    content: str | None = None
    color: str | None = None
    pinned: bool | None = None


@router.get("/memos")
def list_memos():
    state = _materialize()
    memos = list(state.values())
    # Pinned first, then newest first
    memos.sort(key=lambda m: (not m.get("pinned", False), -float(m.get("created_at_ts", 0))))
    return {"memos": memos, "count": len(memos)}


@router.post("/memos")
def create_memo(req: MemoCreate):
    if req.color not in VALID_COLORS:
        raise HTTPException(400, f"color must be one of {VALID_COLORS}")

    now = timestamp_jst()
    memo = {
        "id": generate_id("memo"),
        "content": req.content,
        "color": req.color,
        "pinned": req.pinned,
        "created_at": now,
        "created_at_ts": _ts(now),
        "updated_at": now,
    }
    append_jsonl(MEMOS_FILE, memo)
    return memo


@router.patch("/memos/{memo_id}")
def update_memo(memo_id: str, req: MemoUpdate):
    current = _materialize().get(memo_id)
    if not current:
        raise HTTPException(404, "Memo not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "color" in updates and updates["color"] not in VALID_COLORS:
        raise HTTPException(400, f"color must be one of {VALID_COLORS}")

    new = {**current, **updates, "updated_at": timestamp_jst()}
    append_jsonl(MEMOS_FILE, new)
    return new


@router.delete("/memos/{memo_id}")
def delete_memo(memo_id: str):
    if not _materialize().get(memo_id):
        raise HTTPException(404, "Memo not found")
    append_jsonl(MEMOS_FILE, {"id": memo_id, "_deleted": True, "deleted_at": timestamp_jst()})
    return {"deleted": True, "id": memo_id}


def _ts(iso: str) -> float:
    """Convert ISO string to unix timestamp for sorting."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(iso).timestamp()
    except Exception:
        return 0.0


# ─── Memo → Completion inference (ユーザーの希望機能) ─────────────────────────────

COMPLETION_SIGNALS = [
    "完了", "終わった", "終えた", "提出", "提出した", "提出済", "出した", "送った",
    "報告", "報告した", "済", "done", "finished", "submitted", "片付けた", "やった",
    "終わり", "完了した", "出し終えた",
]


def _has_signal(text: str) -> bool:
    if not text:
        return False
    t = text
    tl = text.lower()
    return any(sig in t or sig.lower() in tl for sig in COMPLETION_SIGNALS)


def _infer_completions(use_llm: bool = False):
    """内部関数。メモから完了を抽出・適用。
    use_llm=True で軽量LLMで構造抽出して精度を上げる（2番の強化）。
    """
    from data_manager import (
        append_jsonl,
        read_jsonl,
        TASKS_FILE,
        MEMOS_FILE,
        timestamp_jst,
        now_jst,
        DATA_DIR,
        generate_id,
    )
    from router import call_ai, DEFAULT_MODELS

    memo_entries = read_jsonl(MEMOS_FILE)
    memo_state: dict[str, dict] = {}
    for e in memo_entries:
        mid = e.get("id")
        if not mid: continue
        if e.get("_deleted"):
            memo_state.pop(mid, None)
            continue
        memo_state[mid] = e
    recent = sorted([m for m in memo_state.values()], key=lambda m: m.get("created_at", ""), reverse=True)[:30]

    task_entries = read_jsonl(TASKS_FILE)
    task_state: dict[str, dict] = {}
    for e in task_entries:
        tid = e.get("id")
        if not tid: continue
        if e.get("_deleted"):
            task_state.pop(tid, None)
            continue
        task_state[tid] = e
    open_tasks = [t for t in task_state.values() if t.get("status") != "done"]

    cal_events: list[dict] = []
    try:
        from gcal import is_configured, list_events_range
        from datetime import timedelta
        d0 = now_jst().strftime("%Y-%m-%d")
        d1 = (now_jst() + timedelta(days=2)).strftime("%Y-%m-%d")
        if is_configured():
            cal_events = list_events_range(start_date=d0, end_date=d1) or []
    except Exception:
        cal_events = []

    applied: list[dict] = []
    today = now_jst().strftime("%Y-%m-%d")

    # LLMでより良い抽出（2. の強化）
    extracted_items: list[str] = []
    if use_llm:
        try:
            signal_memos = [m for m in recent if _has_signal(str(m.get("content", "")))]
            if signal_memos:
                memo_blob = "\n".join(f"- {m.get('id')}: {str(m.get('content',''))[:200]}" for m in signal_memos[:8])
                extract_prompt = """以下のメモから「完了・提出・終わった」などの実績をリストアップせよ。
各行は短いタイトル形式で。JSON配列のみ出力。
例: ["J-SLA原稿提出", "TAシフト提出", "英語IIレポート採点完了"]
"""
                raw = call_ai(
                    messages=[{"role": "user", "content": memo_blob}],
                    system=extract_prompt,
                    engine="gpt",
                    model=DEFAULT_MODELS.get("gpt", "gpt-4o-mini"),
                    max_tokens=400,
                )
                import json as _json, re as _re
                cleaned = _re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
                extracted_items = _json.loads(cleaned) if cleaned.startswith("[") else []
        except Exception:
            extracted_items = []

    for m in recent:
        content = str(m.get("content", ""))
        if not _has_signal(content) and not any(item.lower() in content.lower() for item in extracted_items):
            continue
        cl = content.lower()

        # より賢いマッチ: タイトル or LLM抽出語句
        candidates = [str(t.get("title", "")) for t in open_tasks]
        candidates += extracted_items

        for t in list(open_tasks):
            title = str(t.get("title", ""))
            if not title: continue
            tl = title.lower()
            matched = tl in cl or any(item.lower() in cl or item.lower() in tl for item in extracted_items if item)
            if matched or (len(title) > 3 and title.split()[0].lower() in cl):
                new_task = {
                    **t,
                    "status": "done",
                    "completed_at": timestamp_jst(),
                    "updated_at": timestamp_jst(),
                    "completion_note": f"memo:{m.get('id')} から自動認識" + (" (LLM)" if use_llm else ""),
                }
                append_jsonl(TASKS_FILE, new_task)
                applied.append({"kind": "task", "id": t.get("id"), "title": title, "memo_id": m.get("id"), "via_llm": use_llm})
                open_tasks = [ot for ot in open_tasks if ot.get("id") != t.get("id")]

        for ev in cal_events:
            et = str(ev.get("title") or ev.get("summary") or "")
            if not et: continue
            if et.lower() in cl or any(item.lower() in et.lower() or item.lower() in cl for item in extracted_items):
                try:
                    comp_file = DATA_DIR / "completions.jsonl"
                    entry = {
                        "kind": "calendar",
                        "ref_id": ev.get("id") or et,
                        "title": et,
                        "date": today,
                        "category": "",
                        "note": f"memo:{m.get('id')} から認識: {content[:80]}" + (" (LLM)" if use_llm else ""),
                        "completed_at": timestamp_jst(),
                        "source": "memo-infer" + ("-llm" if use_llm else ""),
                    }
                    append_jsonl(comp_file, entry)
                    applied.append({"kind": "calendar", "id": ev.get("id"), "title": et, "memo_id": m.get("id"), "via_llm": use_llm})
                except Exception:
                    pass

        # 自動 work_log 永続化 (4. の強化)
        try:
            work_file = DATA_DIR / "work_log.jsonl"
            existing = read_jsonl(work_file)
            already = any(
                today in str(w.get("date", "")) and (content[:40] in str(w.get("outcome", "")) or content[:40] in str(w.get("title", "")))
                for w in existing[-25:]
            )
            if not already:
                wlog = {
                    "id": generate_id("work"),
                    "title": (extracted_items[0] if extracted_items else content[:60]) or "memoから実績",
                    "project": "",
                    "category": "",
                    "date": today,
                    "minutes": 0,
                    "engine": "memo-infer" + ("-llm" if use_llm else ""),
                    "outcome": content,
                    "tags": ["from-memo", "auto"],
                    "created_at": timestamp_jst(),
                    "source_memo": m.get("id"),
                }
                append_jsonl(work_file, wlog)
                applied.append({"kind": "work_log", "memo_id": m.get("id"), "via_llm": use_llm})
        except Exception:
            pass

    return {"applied": applied, "count": len(applied), "scanned": len(recent), "llm_used": use_llm}


@router.post("/memos/infer-completions")
def infer_completions(use_llm: bool = False):
    """メモ本文から完了/提出を検知してタスク・カレンダー・work_logを自動認識。
    use_llm=true で軽量LLM抽出を使う（精度向上）。
    1. 予定 vs 実績照合の基盤
    2. LLM強化
    4. 自動永続化
    """
    return _infer_completions(use_llm=use_llm)
