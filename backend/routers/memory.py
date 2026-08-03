"""
GET/POST /api/memory — Memory management (heuristics, decisions, failures, voice, feedback).
"""

from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from data_manager import (
    read_jsonl, append_jsonl, read_yaml, update_yaml,
    DECISIONS_FILE, FAILURES_FILE, FEEDBACK_FILE, VOICE_FILE,
    HEURISTICS_FILE, EXPERIENCES_FILE,
    generate_id, timestamp_jst, now_jst,
)

router = APIRouter()

VALID_DECISION_STATUS = {"active", "closed", "revisit"}


def materialize_decisions() -> list[dict]:
    """decisions.jsonl を id ごと最新に畳む (latest-wins)。

    結果トラッキングは既存の decision と同じ id で {..., status, outcome} を追記する。
    ここで最新状態に潰すので、outcome を後から書いても 1 レコードとして読める。
    """
    state: dict[str, dict] = {}
    order: list[str] = []
    for e in read_jsonl(DECISIONS_FILE):
        did = e.get("id")
        if not did:
            continue
        if did not in state:
            order.append(did)
        if e.get("_deleted"):
            state.pop(did, None)
            continue
        # 既存に上書きマージ (outcome 追記が created 時の本文を消さないように)
        state[did] = {**state.get(did, {}), **e}
    return [state[d] for d in order if d in state]


def _is_pending_outcome(d: dict, cutoff_iso: str) -> bool:
    """結果を観測すべき決定 = 未クローズ・未記入・一定日数が経過。"""
    if (d.get("outcome") or "").strip():
        return False
    if d.get("status") in ("closed", "revisit"):
        return False
    return d.get("timestamp", "") <= cutoff_iso


@router.get("/memory/heuristics")
def get_heuristics():
    """Get current heuristics (rules of thumb)."""
    return read_yaml(HEURISTICS_FILE)


@router.get("/memory/decisions")
def get_decisions():
    """Get decision log (latest-wins, natural/oldest-first order)."""
    # materialize_decisions() は初出 id 順 (≒古い順) を保つ。フロントは reverse で新しい順表示。
    return {"entries": materialize_decisions()}


@router.get("/memory/decisions/pending-outcome")
def get_pending_outcome(days: int = Query(14, ge=1, le=180)):
    """結果を観測すべき決定を新しい順で返す。週次レビューと Daily が拾う。"""
    cutoff_iso = (now_jst() - timedelta(days=days)).isoformat()
    pending = [d for d in materialize_decisions() if _is_pending_outcome(d, cutoff_iso)]
    pending.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"entries": pending, "count": len(pending), "days": days}


class OutcomeEntry(BaseModel):
    outcome: str
    status: str = "closed"  # closed = 決着 / revisit = もう一度考える / active = 継続観察


@router.post("/memory/decisions/{decision_id}/outcome")
def record_outcome(decision_id: str, body: OutcomeEntry):
    """決定に結果を記録する (本人の明示操作)。同 id で追記 = latest-wins で潰れる。"""
    current = {d.get("id"): d for d in materialize_decisions()}
    base = current.get(decision_id)
    if not base:
        raise HTTPException(status_code=404, detail="decision not found")
    status = body.status if body.status in VALID_DECISION_STATUS else "closed"
    record = {
        **base,
        "status": status,
        "outcome": body.outcome,
        "outcome_at": timestamp_jst(),
        "updated_at": timestamp_jst(),
    }
    append_jsonl(DECISIONS_FILE, record)
    return {"ok": True, "decision": record}


@router.get("/memory/failures")
def get_failures():
    """Get failure log."""
    return {"entries": read_jsonl(FAILURES_FILE)}


@router.get("/memory/voice")
def get_voice():
    """Get voice profile observations."""
    return {"entries": read_jsonl(VOICE_FILE)}


@router.get("/memory/feedback")
def get_feedback():
    """Get feedback patterns."""
    return {"entries": read_jsonl(FEEDBACK_FILE)}


@router.get("/memory/experiences")
def get_experiences():
    """Get experiences."""
    return {"entries": read_jsonl(EXPERIENCES_FILE)}


class DecisionEntry(BaseModel):
    title: str
    context: str
    options: list[str] = []
    chosen: str = ""
    reasoning: str = ""
    domain: str = "personal"


@router.post("/memory/decisions")
def add_decision(entry: DecisionEntry):
    """Log a key decision."""
    record = {
        "id": generate_id("dec"),
        "timestamp": timestamp_jst(),
        **entry.model_dump(),
    }
    append_jsonl(DECISIONS_FILE, record)
    return record


class FailureEntry(BaseModel):
    what_happened: str
    why: str = ""
    lesson: str = ""
    domain: str = "personal"


@router.post("/memory/failures")
def add_failure(entry: FailureEntry):
    """Log a failure with lesson learned."""
    record = {
        "id": generate_id("fail"),
        "timestamp": timestamp_jst(),
        **entry.model_dump(),
    }
    append_jsonl(FAILURES_FILE, record)
    return record
