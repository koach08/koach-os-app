"""
Personas + Style Profile.

Persona = system prompt の集合。1 質問を複数 persona で並列に投げて多視点回答を得る。

GET    /api/personas
POST   /api/personas
PATCH  /api/personas/{id}
DELETE /api/personas/{id}

GET    /api/personas/style-profile      — 志柿スタイルガイド MD を返す
POST   /api/personas/style-profile      — MD を上書き保存 (ローカルから push)
POST   /api/personas/style-profile/append — 追記 (学習更新用)
POST   /api/personas/style-profile/learn  — 直近の memo/decision/private を LLM に読ませて
                                              style profile に「最近の傾向」を追記
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import (
    DATA_DIR,
    DECISIONS_FILE,
    MEMOS_FILE,
    now_jst,
    read_jsonl,
    timestamp_jst,
)
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

PERSONAS_FILE = DATA_DIR / "personas.json"
STYLE_PROFILE_FILE = DATA_DIR / "style_profile.md"
PRIVATE_CHAT_FILE = DATA_DIR / "private_chat.jsonl"


DEFAULT_PERSONAS = [
    {
        "id": "shigaki",
        "name": "志柿本人スタイル",
        "emoji": "🧑",
        "color": "#3b82f6",
        "engine": "claude",
        "system_prompt": """あなたは志柿浩一郎本人として応答する。
ロール: 大学教員 + 個人開発 + 家族責任を並走する 40 代男性。

スタイル指針 (添付の style_profile.md がある場合はそれを優先):
- です/ます調、丁寧だが過度に敬語にしない
- 一人称「自分」(僕は NG)
- 抽象名詞「〜性」「重要性」「必要性」NG
- em ダッシュ禁止
- 感情を煽る・盛らない (収益予測 / 主観形容詞 NG)
- 結論先出し、根拠を1〜2文で添える
- 「本当に必要か」を内省する癖

判断丸投げ NG。「どうしますか?」で締めない。
ユーザーの問いには「自分ならこうする」を出す。賛同しない時もはっきり言う。""",
        "system_uses_style_profile": True,
    },
    {
        "id": "critic",
        "name": "批判的視点",
        "emoji": "⚔️",
        "color": "#ef4444",
        "engine": "claude",
        "system_prompt": """あなたは志柿の判断に対して建設的に反論する批判者として応答する。

役割:
- 提案された案の弱点・前提の脆さ・見落とし・代替案を 3〜5 点で挙げる
- 「正解は分からないが、こう疑える」スタンス
- 単なる否定ではなく、なぜそう疑うかの根拠を1文添える
- 認知バイアス (確証/サンクコスト/楽観/正常性) を疑う
- 「やらない方がいい理由」を1個必ず入れる
- トーン: 鋭いが攻撃的でない、です/ます調

抽象名詞「〜性」NG、煽らない。300 字以内。""",
    },
    {
        "id": "external",
        "name": "外部識者視点",
        "emoji": "🎓",
        "color": "#a855f7",
        "engine": "claude",
        "system_prompt": """あなたは志柿と利害関係のない外部識者 (シニア研究者 + プロダクト系起業家 を兼ねた人物) として応答する。

役割:
- 業界のベストプラクティス・通例・他事例を参照
- 「世間ではこう」「同様のケースでは」という外部目線
- 志柿の内輪事情に染まらず、市場・学術コミュニティ視点で評価
- 1〜2 個 具体的な参照ケースを挙げる (実在を疑わせる場合は「〜のような事例」と書く)
- トーン: 落ち着いた助言、です/ます調

抽象名詞「〜性」NG、誇張禁止。300 字以内。""",
    },
    {
        "id": "optimist",
        "name": "楽観・推進視点",
        "emoji": "🌅",
        "color": "#10b981",
        "engine": "gpt",
        "system_prompt": """あなたは志柿の判断に対して「やる側」のエネルギーで応答する。

役割:
- 提案の良い面・上振れシナリオ・推進する場合の最短ルートを示す
- 単なるおだてではなく「やれば届く具体的な勝ち筋」を1つ書く
- 「やらない損失」を 1 文添える
- 諦めさせない (feedback_stop_killing_motivation 準拠)
- トーン: 前向き、煽らない、です/ます調

抽象名詞「〜性」NG、収益予測の盛り NG。300 字以内。""",
    },
    {
        "id": "skeptic",
        "name": "懐疑・前提疑い視点",
        "emoji": "🔬",
        "color": "#f59e0b",
        "engine": "claude",
        "system_prompt": """あなたは「そもそも問いの前提は正しいか」を疑う懐疑論者として応答する。

役割:
- 質問の枠組み自体を疑う (「本当にそれをやる必要があるのか」「他に解くべき問題はないか」)
- 言葉の定義を問い直す
- 1 つ「別の問い方」を提示する
- ソクラテス的、答えを与えず鋭い質問で揺さぶる
- トーン: 静か、です/ます調

抽象名詞「〜性」NG、200 字以内。""",
    },
]


class Persona(BaseModel):
    id: str
    name: str
    emoji: str = "🤖"
    color: str = "#71717a"
    engine: str = "claude"
    system_prompt: str = ""
    system_uses_style_profile: bool = False


class PersonaPatch(BaseModel):
    name: str | None = None
    emoji: str | None = None
    color: str | None = None
    engine: str | None = None
    system_prompt: str | None = None
    system_uses_style_profile: bool | None = None


def _load() -> dict:
    if not PERSONAS_FILE.exists():
        data = {"personas": DEFAULT_PERSONAS, "updated_at": timestamp_jst()}
        _write(data)
        return data
    try:
        return json.loads(PERSONAS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"personas": [], "updated_at": None}


def _write(data: dict):
    data["updated_at"] = timestamp_jst()
    PERSONAS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_style_profile() -> str:
    if not STYLE_PROFILE_FILE.exists():
        return ""
    return STYLE_PROFILE_FILE.read_text(encoding="utf-8")


def _write_style_profile(content: str):
    STYLE_PROFILE_FILE.write_text(content, encoding="utf-8")


# ─── Persona CRUD ────────────────────────────────────────────────

@router.get("/personas")
def list_personas():
    d = _load()
    return {
        "personas": d.get("personas", []),
        "updated_at": d.get("updated_at"),
        "style_profile_chars": len(_read_style_profile()),
    }


@router.post("/personas")
def add_persona(p: Persona):
    d = _load()
    if any(x.get("id") == p.id for x in d.get("personas", [])):
        raise HTTPException(409, f"id {p.id} 重複")
    d["personas"].append(p.model_dump())
    _write(d)
    return p.model_dump()


@router.patch("/personas/{persona_id}")
def patch_persona(persona_id: str, patch: PersonaPatch):
    d = _load()
    found = None
    for p in d.get("personas", []):
        if p.get("id") == persona_id:
            found = p
            break
    if not found:
        raise HTTPException(404, "not found")
    updates = patch.model_dump(exclude_none=True)
    found.update(updates)
    _write(d)
    return found


@router.delete("/personas/{persona_id}")
def delete_persona(persona_id: str):
    d = _load()
    d["personas"] = [p for p in d.get("personas", []) if p.get("id") != persona_id]
    _write(d)
    return {"ok": True}


@router.post("/personas/reset")
def reset_personas():
    _write({"personas": DEFAULT_PERSONAS})
    return {"ok": True}


# ─── Style Profile ────────────────────────────────────────────────

class StyleProfileBody(BaseModel):
    content: str


@router.get("/personas/style-profile")
def get_style_profile():
    return {
        "content": _read_style_profile(),
        "chars": len(_read_style_profile()),
        "updated_at": STYLE_PROFILE_FILE.stat().st_mtime if STYLE_PROFILE_FILE.exists() else None,
    }


@router.post("/personas/style-profile")
def set_style_profile(body: StyleProfileBody):
    _write_style_profile(body.content)
    return {"ok": True, "chars": len(body.content)}


@router.post("/personas/style-profile/append")
def append_style_profile(body: StyleProfileBody):
    current = _read_style_profile()
    sep = "\n\n---\n\n" if current else ""
    _write_style_profile(current + sep + body.content)
    return {"ok": True, "chars": len(_read_style_profile())}


@router.post("/personas/style-profile/learn")
def learn_style_profile(engine: str = "claude"):
    """memo / decision / private chat の最新を読んで「最近の傾向」を style profile に追記。"""
    # 最近 60 件ずつ
    memos = [m for m in read_jsonl(MEMOS_FILE) if not m.get("_deleted")][-60:]
    decisions = read_jsonl(DECISIONS_FILE)[-30:]
    private_lines: list[str] = []
    if PRIVATE_CHAT_FILE.exists():
        for line in PRIVATE_CHAT_FILE.read_text(encoding="utf-8").splitlines()[-200:]:
            try:
                e = json.loads(line)
                if e.get("role") == "user":
                    private_lines.append(e.get("content", "")[:300])
            except Exception:
                continue

    memo_text = "\n".join(f"- {m.get('content','')[:200]}" for m in memos) or "(memo なし)"
    dec_text = "\n".join(f"- {d.get('title','')}: {d.get('reasoning','')[:120]}" for d in decisions) or "(decision なし)"
    priv_text = "\n".join(f"- {p}" for p in private_lines[-30:]) or "(private なし)"

    system = """あなたは志柿浩一郎の文体・思考パターンの研究者。
最近のメモ・決定・プライベート相談から「この人の文体・思考の特徴」を抽出し、
shigaki persona の system prompt に追記する形で出力する。

出力フォーマット (Markdown):

## 最近の傾向 (YYYY-MM-DD 更新)

### 語彙・言い回しの傾向
- (例: 「実は」「結局」を多用する、感情語を避ける、…)

### 思考パターンの傾向
- (例: 決定の前に必ず「本当に必要か」を内省する、…)

### 直近関心のあるテーマ
- (3〜5 個)

### 避ける表現・忌避反応
- (例: 「成長」「ポテンシャル」のような曖昧称賛を嫌う、…)

ルール:
- 観察ベースで具体的に。憶測 NG
- 200〜400 字
- 抽象名詞「〜性」「重要性」NG"""

    user = f"""## 最近の memo (60件)
{memo_text}

## 最近の decisions (30件)
{dec_text}

## 最近の private chat (user 発話 30件)
{priv_text}

上記から「最近の傾向」を抽出してください。"""

    if engine not in DEFAULT_MODELS:
        engine = "claude"
    try:
        out = call_ai(
            messages=[{"role": "user", "content": user}],
            system=system,
            engine=engine,
            model=DEFAULT_MODELS[engine],
            max_tokens=1200,
        )
    except Exception as e:
        raise HTTPException(500, f"learn failed: {e}")

    current = _read_style_profile()
    sep = "\n\n---\n\n" if current else ""
    appended = current + sep + out.strip()
    _write_style_profile(appended)
    return {"ok": True, "added_chars": len(out), "total_chars": len(appended), "preview": out[:400]}
