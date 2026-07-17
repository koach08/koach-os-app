"""
KB Proposals — Consolidate ジョブが出した構造化下書きのレビューキュー。
承認【1タップ】で decisions に昇格する。これで「発見→構造化→承認して定着」のループが
書き込みまで閉じる。autopilot は提案のみ (自動書込ゼロ) を維持し、実データへの反映は
本人の明示操作 (promote) だけが行う。

保管: append-only + latest-wins(id)。status: pending → promoted | rejected。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data_manager import (
    DATA_DIR, DECISIONS_FILE,
    read_jsonl, append_jsonl, init_jsonl, generate_id, timestamp_jst,
)

router = APIRouter()

KB_PROPOSALS_FILE = DATA_DIR / "kb_proposals.jsonl"
init_jsonl(KB_PROPOSALS_FILE, "kb_proposals", "Consolidate が出した構造化下書きのレビューキュー")

VALID_DOMAINS = {"personal", "research", "platform", "revenue", "teaching"}
VALID_KINDS = {"decision", "concept", "failure"}


def _materialize() -> dict[str, dict]:
    """JSONL を id ごとの最新状態に畳む (latest-wins)。"""
    state: dict[str, dict] = {}
    for e in read_jsonl(KB_PROPOSALS_FILE):
        pid = e.get("id")
        if not pid:
            continue
        if e.get("_deleted"):
            state.pop(pid, None)
            continue
        state[pid] = e
    return state


def add_proposal(p: dict) -> dict | None:
    """Consolidate ジョブから呼ぶ。pending/promoted と title 重複するものはスキップ (dedup)。"""
    title = (p.get("title") or "").strip()
    if not title:
        return None
    for e in _materialize().values():
        if e.get("status") in ("pending", "promoted") and \
                (e.get("title", "").strip().lower() == title.lower()):
            return None
    kind = p.get("kind") if p.get("kind") in VALID_KINDS else "decision"
    domain = p.get("domain") if p.get("domain") in VALID_DOMAINS else "personal"
    opts = p.get("options") or []
    if not isinstance(opts, list):
        opts = [str(opts)]
    rec = {
        "id": generate_id("kbp"),
        "kind": kind,
        "title": title,
        "context": str(p.get("context", "")),
        "options": [str(o) for o in opts],
        "chosen": str(p.get("chosen", "")),
        "reasoning": str(p.get("reasoning", "")),
        "domain": domain,
        "status": "pending",
        "source": "consolidate",
        "created_at": timestamp_jst(),
    }
    append_jsonl(KB_PROPOSALS_FILE, rec)
    return rec


# ─── routes ───

@router.get("/proposals")
def list_proposals(status: str = Query("pending", description="pending|promoted|rejected|(空で全部)")):
    items = list(_materialize().values())
    if status:
        items = [e for e in items if e.get("status") == status]
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"items": items, "count": len(items)}


@router.get("/proposals/counts")
def proposal_counts():
    items = _materialize().values()
    out = {"pending": 0, "promoted": 0, "rejected": 0}
    for e in items:
        s = e.get("status", "")
        if s in out:
            out[s] += 1
    return out


@router.post("/proposals/{pid}/promote")
def promote_proposal(pid: str):
    """承認 = decisions に本書き込み。実データへの反映はこの明示操作でだけ起きる。"""
    st = _materialize()
    p = st.get(pid)
    if not p:
        raise HTTPException(status_code=404, detail="proposal not found")
    if p.get("status") == "promoted":
        return {"ok": True, "already": True, "decision_id": p.get("promoted_decision_id")}

    decision = {
        "id": generate_id("dec"),
        "timestamp": timestamp_jst(),
        "title": p.get("title", ""),
        "context": p.get("context", ""),
        "options": p.get("options", []),
        "chosen": p.get("chosen", ""),
        "reasoning": p.get("reasoning", ""),
        "domain": p.get("domain", "personal"),
        "source": "consolidate-promote",
        "from_proposal": pid,
    }
    append_jsonl(DECISIONS_FILE, decision)

    updated = {**p, "status": "promoted", "promoted_decision_id": decision["id"],
               "updated_at": timestamp_jst()}
    append_jsonl(KB_PROPOSALS_FILE, updated)
    return {"ok": True, "decision_id": decision["id"], "decision": decision}


@router.post("/proposals/{pid}/reject")
def reject_proposal(pid: str):
    st = _materialize()
    p = st.get(pid)
    if not p:
        raise HTTPException(status_code=404, detail="proposal not found")
    updated = {**p, "status": "rejected", "updated_at": timestamp_jst()}
    append_jsonl(KB_PROPOSALS_FILE, updated)
    return {"ok": True}


class EditIn(BaseModel):
    title: str | None = None
    context: str | None = None
    options: list[str] | None = None
    chosen: str | None = None
    reasoning: str | None = None
    domain: str | None = None


@router.patch("/proposals/{pid}")
def edit_proposal(pid: str, patch: EditIn):
    """昇格前に下書きを手直しする (pending のみ)。"""
    st = _materialize()
    p = st.get(pid)
    if not p:
        raise HTTPException(status_code=404, detail="proposal not found")
    if p.get("status") != "pending":
        raise HTTPException(status_code=400, detail="pending 以外は編集不可")
    data = patch.model_dump(exclude_none=True)
    if "domain" in data and data["domain"] not in VALID_DOMAINS:
        data.pop("domain")
    updated = {**p, **data, "updated_at": timestamp_jst()}
    append_jsonl(KB_PROPOSALS_FILE, updated)
    return {"ok": True, "proposal": updated}
