"""
GET/POST/PATCH/DELETE /api/work-log — 実績台帳 (work log)。

memos とは別物。memos は「走り書き・断片」、work_log は「やり遂げたこと」の永続記録。
完了した意味のある作業を、プロジェクト / カテゴリ / かかった時間 / 使った AI エンジン /
成果メモ付きで時系列に積む。patterns.py の分析と dispatch_auto.py の学習提案の土台になる。

Append-only JSONL、最新エントリ勝ち、tombstone 削除 (memos / completions と同じ作法)。
既存ファイルには触らない。新規ファイル data/work_log.jsonl のみ。
"""

from __future__ import annotations

from datetime import date as date_cls, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data_manager import (
    DATA_DIR,
    append_jsonl,
    init_jsonl,
    read_jsonl,
    generate_id,
    now_jst,
    timestamp_jst,
)

router = APIRouter()

WORK_LOG_FILE = DATA_DIR / "work_log.jsonl"
init_jsonl(WORK_LOG_FILE, "work_log", "やり遂げた作業の永続台帳 (AI エンジンタグ付き)")

# 実作業で使う AI ツール候補 (フロントの dropdown 用)。
# DEFAULT_MODELS の API エンジンに加え、ブラウザ/デスクトップで使うツールも含む。
ENGINE_OPTIONS = [
    "claude-code",
    "claude",
    "gpt",
    "gemini",
    "grok",
    "perplexity",
    "venice",
    "canva",
    "notebooklm",
    "codex",
    "none",
    "other",
]


def _today_jst() -> str:
    return now_jst().strftime("%Y-%m-%d")


def _materialize() -> dict[str, dict]:
    state: dict[str, dict] = {}
    for e in read_jsonl(WORK_LOG_FILE):
        wid = e.get("id")
        if not wid:
            continue
        if e.get("_deleted"):
            state.pop(wid, None)
            continue
        state[wid] = e
    return state


class WorkLogCreate(BaseModel):
    title: str
    project: str = ""
    category: str = ""
    date: str = ""        # YYYY-MM-DD; defaults to today JST
    minutes: int = 0       # かかった時間 (任意)
    engine: str = ""       # 使った AI (任意, ENGINE_OPTIONS のどれか or 自由文)
    outcome: str = ""      # 成果 / メモ
    tags: list[str] = []


class WorkLogUpdate(BaseModel):
    title: str | None = None
    project: str | None = None
    category: str | None = None
    date: str | None = None
    minutes: int | None = None
    engine: str | None = None
    outcome: str | None = None
    tags: list[str] | None = None


class PromoteFromCompletion(BaseModel):
    title: str
    project: str = ""
    category: str = ""
    date: str = ""
    engine: str = ""
    outcome: str = ""
    ref_id: str = ""       # 元 completion の参照 (重複昇格の検出用)


def _validate_date(d: str) -> str:
    target = d or _today_jst()
    try:
        date_cls.fromisoformat(target)
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    return target


@router.get("/work-log")
def list_work_log(
    project: str = Query(""),
    category: str = Query(""),
    engine: str = Query(""),
    start: str = Query("", description="YYYY-MM-DD 以降"),
    end: str = Query("", description="YYYY-MM-DD 以前"),
    q: str = Query("", description="title / outcome の部分一致"),
    limit: int = Query(200, ge=1, le=1000),
):
    items = list(_materialize().values())

    if project:
        items = [w for w in items if w.get("project") == project]
    if category:
        items = [w for w in items if w.get("category") == category]
    if engine:
        items = [w for w in items if w.get("engine") == engine]
    if start:
        items = [w for w in items if w.get("date", "") >= start]
    if end:
        items = [w for w in items if w.get("date", "") <= end]
    if q:
        s = q.lower()
        items = [
            w for w in items
            if s in (w.get("title", "") or "").lower()
            or s in (w.get("outcome", "") or "").lower()
        ]

    # 新しい日付順 → 同日は登録の新しい順
    items.sort(key=lambda w: (w.get("date", ""), w.get("created_at", "")), reverse=True)
    return {"items": items[:limit], "count": len(items)}


@router.get("/work-log/facets")
def work_log_facets():
    """フィルタ用の既存プロジェクト / カテゴリ一覧 + エンジン候補。"""
    items = _materialize().values()
    projects = sorted({w.get("project", "") for w in items if w.get("project")})
    categories = sorted({w.get("category", "") for w in items if w.get("category")})
    return {"projects": projects, "categories": categories, "engines": ENGINE_OPTIONS}


@router.get("/work-log/stats")
def work_log_stats(days: int = Query(90, ge=1, le=3650)):
    """実績の集計。「どの作業にどの AI を使ったか」を炙り出す
    = エンジン学習提案 (dispatch_auto との連携) の土台。"""
    cutoff = (now_jst().date() - timedelta(days=days - 1)).isoformat()
    items = [w for w in _materialize().values() if w.get("date", "") >= cutoff]

    by_project: dict[str, dict] = {}
    by_category: dict[str, dict] = {}
    by_engine: dict[str, int] = {}
    # category -> engine -> count (「この種の作業で何を使っているか」)
    engine_by_category: dict[str, dict[str, int]] = {}
    total_minutes = 0

    for w in items:
        proj = w.get("project") or "(未分類)"
        cat = w.get("category") or "(未分類)"
        eng = w.get("engine") or "none"
        mins = int(w.get("minutes") or 0)
        total_minutes += mins

        bp = by_project.setdefault(proj, {"count": 0, "minutes": 0})
        bp["count"] += 1
        bp["minutes"] += mins

        bc = by_category.setdefault(cat, {"count": 0, "minutes": 0})
        bc["count"] += 1
        bc["minutes"] += mins

        by_engine[eng] = by_engine.get(eng, 0) + 1
        ebc = engine_by_category.setdefault(cat, {})
        ebc[eng] = ebc.get(eng, 0) + 1

    return {
        "days": days,
        "total_entries": len(items),
        "total_minutes": total_minutes,
        "by_project": by_project,
        "by_category": by_category,
        "by_engine": by_engine,
        "engine_by_category": engine_by_category,
    }


@router.post("/work-log")
def create_work_log(req: WorkLogCreate):
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="title required")
    target_date = _validate_date(req.date)
    now = timestamp_jst()
    entry = {
        "id": generate_id("work"),
        "title": req.title.strip(),
        "project": req.project.strip(),
        "category": req.category.strip(),
        "date": target_date,
        "minutes": max(0, req.minutes),
        "engine": req.engine.strip(),
        "outcome": req.outcome.strip(),
        "tags": [t.strip() for t in req.tags if t.strip()],
        "source": "manual",
        "created_at": now,
        "updated_at": now,
    }
    append_jsonl(WORK_LOG_FILE, entry)
    return entry


@router.post("/work-log/from-completion")
def promote_from_completion(req: PromoteFromCompletion):
    """Daily Brief / Evening で done にした項目を実績台帳へ昇格。
    同じ ref_id + date が既に昇格済みなら二重登録しない (冪等)。"""
    if not req.title.strip():
        raise HTTPException(status_code=400, detail="title required")
    target_date = _validate_date(req.date)

    if req.ref_id:
        for w in _materialize().values():
            if w.get("ref_id") == req.ref_id and w.get("date") == target_date:
                return {"created": False, "existing": w}

    now = timestamp_jst()
    entry = {
        "id": generate_id("work"),
        "title": req.title.strip(),
        "project": req.project.strip(),
        "category": req.category.strip(),
        "date": target_date,
        "minutes": 0,
        "engine": req.engine.strip(),
        "outcome": req.outcome.strip(),
        "tags": [],
        "source": "completion",
        "ref_id": req.ref_id,
        "created_at": now,
        "updated_at": now,
    }
    append_jsonl(WORK_LOG_FILE, entry)
    return {"created": True, "entry": entry}


@router.patch("/work-log/{work_id}")
def update_work_log(work_id: str, req: WorkLogUpdate):
    current = _materialize().get(work_id)
    if not current:
        raise HTTPException(status_code=404, detail="work log entry not found")

    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    if "date" in updates:
        updates["date"] = _validate_date(updates["date"])
    if "minutes" in updates:
        updates["minutes"] = max(0, int(updates["minutes"]))
    if "tags" in updates:
        updates["tags"] = [t.strip() for t in updates["tags"] if t.strip()]

    new = {**current, **updates, "updated_at": timestamp_jst()}
    append_jsonl(WORK_LOG_FILE, new)
    return new


@router.delete("/work-log/{work_id}")
def delete_work_log(work_id: str):
    if not _materialize().get(work_id):
        raise HTTPException(status_code=404, detail="work log entry not found")
    append_jsonl(WORK_LOG_FILE, {"id": work_id, "_deleted": True, "deleted_at": timestamp_jst()})
    return {"deleted": True, "id": work_id}
