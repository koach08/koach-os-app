"""
POST /api/persona-chat — 1 質問を複数 persona に並列で投げる。

body: { question, persona_ids: ["shigaki", "critic", "external"], engine_override?: str }
return: { answers: [{persona_id, name, emoji, color, answer, engine_used}], generated_at }
"""

from __future__ import annotations

import concurrent.futures as cf
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import now_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()


class PersonaChatReq(BaseModel):
    question: str
    persona_ids: list[str] = []
    engine_override: str | None = None
    context: str = ""  # 追加コンテキスト (memo / decision の抜粋など)


def _load_personas() -> list[dict]:
    from routers.personas import _load
    return _load().get("personas", [])


def _resolve_system(p: dict) -> str:
    base = p.get("system_prompt", "") or ""
    if p.get("system_uses_style_profile"):
        from routers.personas import _read_style_profile
        style = _read_style_profile().strip()
        if style:
            base += "\n\n## 追加: 志柿スタイルガイド (常に優先)\n" + style
    return base


def _ask(p: dict, question: str, engine_override: str | None, context: str) -> dict:
    engine = engine_override or p.get("engine", "claude")
    if engine not in DEFAULT_MODELS:
        engine = "claude"
    model = DEFAULT_MODELS[engine]
    system = _resolve_system(p)
    user_msg = question if not context else f"## 追加コンテキスト\n{context}\n\n## 問い\n{question}"
    try:
        answer = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=system,
            engine=engine,
            model=model,
            max_tokens=1200,
        )
    except Exception as e:
        answer = f"(生成失敗: {e})"
    return {
        "persona_id": p["id"],
        "name": p.get("name", ""),
        "emoji": p.get("emoji", "🤖"),
        "color": p.get("color", "#71717a"),
        "engine_used": engine,
        "model_used": model,
        "answer": answer,
    }


@router.post("/persona-chat")
def persona_chat(req: PersonaChatReq):
    if not req.question.strip():
        raise HTTPException(400, "question 必須")
    all_personas = _load_personas()
    ids = req.persona_ids or [p["id"] for p in all_personas]
    selected = [p for p in all_personas if p["id"] in ids]
    if not selected:
        raise HTTPException(400, "該当 persona なし")

    # 並列に投げる (順序は ids 順に揃える)
    with cf.ThreadPoolExecutor(max_workers=min(8, len(selected))) as ex:
        results = list(
            ex.map(
                lambda p: _ask(p, req.question, req.engine_override, req.context),
                selected,
            )
        )
    # ids 順に整列
    order = {pid: i for i, pid in enumerate(ids)}
    results.sort(key=lambda r: order.get(r["persona_id"], 999))
    return {
        "answers": results,
        "generated_at": now_jst().isoformat(),
        "question": req.question,
    }
