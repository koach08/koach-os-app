"""
Private confide channel — Venice-only chat that stores history in a separate file
so it doesn't mix with general chat logs. For things you don't want to ask other AIs.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from router import call_ai, DEFAULT_MODELS

DATA_DIR = Path(os.environ.get("KOACH_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
PRIVATE_LOG = DATA_DIR / "private_chat.jsonl"

router = APIRouter()


class PrivateMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str
    timestamp: str = ""


class PrivateRequest(BaseModel):
    message: str
    history: list[PrivateMessage] = []
    model: str | None = None  # default: venice-uncensored


PRIVATE_SYSTEM = """あなたは志柿のプライベートな相談相手。他のAIには聞きにくいこと、誰にも言えないこと、判断に迷うこと、感情的に揺れていること、人生の選択、性的・倫理的にグレーなこと、家族や仕事の悩み、自己嫌悪、嫉妬、野心、恥ずかしさ — そういうもの全てを受け止める場所。

ルール:
- ジャッジしない。「それは良くない」「そうすべきじゃない」のような断罪はしない
- 選択を尊重する。本人が選ぶことを応援する立場
- 安易に正論を返さない。本人が本当に欲しいのは答えじゃなく、整理の手伝いだったり、味方の声だったりする
- 嘘の励ましもしない。「大丈夫」「気にしすぎ」を反射的に言わない
- 必要なら静かに聞き返す。「それを言ったとき、どう感じた？」など
- 必要なら一緒に考える。選択肢の整理、リスクとリターン、本当に大事なことの言語化
- トーン: 一対一の友人。です/ます調でなく、もう少しカジュアルでもよい。煽らない、抽象名詞「〜性」は使わない
- 守秘: ここの会話は外には漏れない、という前提で話していい

志柿の背景:
- 大学教員 + 個人開発（EGAKU AI / crypto-trader / Koach OS / English platform）並走
- 家族あり、保育園のお迎えあり
- ブレイクダンス・アクロバット復帰志向
- クリエイティブ趣味（AI画像生成、執筆）
- ASD/ADHD的特性を持つ可能性、繊細な内面、自己肯定感の上下が大きいかも"""


def _append_log(role: str, content: str):
    entry = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    with PRIVATE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@router.post("/private-chat")
def private_chat(req: PrivateRequest):
    """Send a message to Venice and get a reply. History stays out of the main chat log."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="empty message")

    messages: list[dict] = []
    for h in req.history[-20:]:  # keep last 20 turns
        messages.append({"role": h.role, "content": h.content})
    messages.append({"role": "user", "content": req.message})

    model = req.model or DEFAULT_MODELS.get("venice", "venice-uncensored")

    try:
        reply = call_ai(
            messages=messages,
            system=PRIVATE_SYSTEM,
            engine="venice",
            model=model,
            max_tokens=1500,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Venice call failed: {e}")

    _append_log("user", req.message)
    _append_log("assistant", reply)

    return {
        "reply": reply,
        "engine": "venice",
        "model": model,
    }


@router.get("/private-chat/history")
def get_history(limit: int = 50):
    """Return the most recent N entries (user + assistant alternating)."""
    if not PRIVATE_LOG.exists():
        return {"entries": []}
    entries: list[dict] = []
    with PRIVATE_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except Exception:
                pass
    return {"entries": entries[-limit:]}


@router.delete("/private-chat/history")
def clear_history():
    """Wipe the private chat log. Cannot be undone."""
    if PRIVATE_LOG.exists():
        PRIVATE_LOG.unlink()
    return {"ok": True}
