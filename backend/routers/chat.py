"""
POST /api/chat — Main chat endpoint with SSE streaming.
"""

import json
import time
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from router import detect_task_type, route, call_ai, DEFAULT_MODELS
from prompts import build_system_prompt
from bias_detector import detect_biases, detect_intervention_level
from learning_engine import (
    get_acceptance_recommendation,
    get_recent_voice_observations,
    get_recent_feedback_patterns,
)
from data_manager import append_jsonl, LOGS_FILE, generate_id, timestamp_jst

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    domain: str = "personal"
    level_override: str | None = None
    engine_override: str | None = None
    acceptance_gradient: str | None = None
    history: list[dict] = []


@router.post("/chat")
async def chat(req: ChatRequest):
    """Process chat message and return SSE stream."""
    user_input = req.message

    # 1. Detect task type & route
    task_type = detect_task_type(user_input, req.domain)
    routing = route(task_type, override=req.engine_override)

    # 2. Detect biases & intervention level
    biases = detect_biases(user_input)
    auto_level, axes = detect_intervention_level(user_input)
    level = req.level_override or auto_level

    # 3. Acceptance gradient
    gradient = req.acceptance_gradient or get_acceptance_recommendation()

    # 4. Build system prompt
    system_prompt = build_system_prompt(
        domain=req.domain,
        intervention_level=level,
        detected_biases=biases,
        routing_engine=routing["engine"],
        acceptance_gradient=gradient,
        recent_feedback_patterns=get_recent_feedback_patterns(3),
        recent_voice_observations=get_recent_voice_observations(3),
    )

    # 5. Build messages
    messages = []
    for h in req.history[-20:]:
        messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
    messages.append({"role": "user", "content": user_input})

    # 6. Call AI
    ai_response = call_ai(messages, system_prompt, routing["engine"], routing["model"])

    # 7. Log interaction (FULL content, not just preview — 2026-06-02 fix:
    # user 入力をメモのつもりで打ったのに 100 文字 truncate で失われていた事故への対応)
    log_entry = {
        "id": generate_id("log"),
        "timestamp": timestamp_jst(),
        "domain": req.domain,
        "intervention_level": level,
        "routing": routing,
        "cognitive_biases": {
            "detected": [b["id"] for b in biases],
            "labels": [b["label"] for b in biases],
        },
        "axes_triggered": axes,
        "acceptance_gradient": gradient,
        "user_input_preview": user_input[:100],   # 後方互換 (UI が preview を読んでる場合用)
        "ai_response_preview": ai_response[:100] if isinstance(ai_response, str) else "",
        "user_input": user_input,                 # 完全版を保存
        "ai_response": ai_response if isinstance(ai_response, str) else "",
        "task_type": task_type,
    }
    append_jsonl(LOGS_FILE, log_entry)

    # 長文入力 (300 文字超かつ "?" で始まらない、= 質問ではなく独白/メモ的) は memos にも自動保存
    # → user は chat に書いたのに memos に残らないという事故を二度と起こさない
    if len(user_input.strip()) >= 300 and not user_input.strip().startswith(("?", "？")):
        try:
            from data_manager import MEMOS_FILE, now_jst
            ts = timestamp_jst()
            memo_entry = {
                "id": f"memo_chat_{int(now_jst().timestamp() * 1000)}",
                "content": user_input,
                "color": "blue",
                "pinned": False,
                "created_at": ts,
                "created_at_ts": int(now_jst().timestamp() * 1000),
                "updated_at": ts,
                "source": "chat_long_input",
            }
            append_jsonl(MEMOS_FILE, memo_entry)
        except Exception:
            pass  # memo 保存失敗しても chat レスポンスは出す

    # 8. SSE streaming response
    metadata = {
        "engine": routing["engine"],
        "model": routing["model"],
        "level": level,
        "biases": [b["label"] for b in biases],
        "task_type": task_type,
        "gradient": gradient,
    }

    def stream_response():
        # Send metadata first
        yield f"data: {json.dumps({'type': 'metadata', 'data': metadata})}\n\n"

        # Stream text in chunks for typing effect
        chunk_size = 3
        for i in range(0, len(ai_response), chunk_size):
            chunk = ai_response[i : i + chunk_size]
            yield f"data: {json.dumps({'type': 'text', 'data': chunk})}\n\n"

        # Done
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
