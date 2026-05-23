"""
Productivity coach — weekly planning AI.

Combines Google Calendar fixed events + user-entered ToDo backlog + recurring life-blocks
(保育園お迎え、家族時間、健康、趣味) to suggest a balanced weekly schedule and
recommend which AI to use for each cognitively-heavy task.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import now_jst
from router import call_ai, DEFAULT_MODELS

DATA_DIR = Path(os.environ.get("KOACH_DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKLOG_PATH = DATA_DIR / "productivity_backlog.json"
LIFE_BLOCKS_PATH = DATA_DIR / "life_blocks.json"

router = APIRouter()


# ─── Models ──────────────────────────────────────────────────────────────────
Category = Literal[
    "career", "research", "creative", "family", "health", "learning", "side_project", "admin", "rest", "other"
]

CATEGORY_META = {
    "career": ("💼", "キャリア"),
    "research": ("🔬", "研究"),
    "creative": ("🎨", "クリエイティブ"),
    "family": ("👨‍👩‍👧", "家族"),
    "health": ("💪", "健康 / ブレイクダンス・アクロバット"),
    "learning": ("📚", "学習"),
    "side_project": ("🚀", "副プロジェクト"),
    "admin": ("📋", "事務"),
    "rest": ("🌙", "休息"),
    "other": ("✨", "その他"),
}


class BacklogItem(BaseModel):
    id: str = ""
    title: str
    category: Category = "other"
    estimated_minutes: int = 60
    urgency: Literal["high", "medium", "low"] = "medium"
    notes: str = ""
    needs_ai: bool = False  # if True, AI tool recommendation will be requested
    done: bool = False


class LifeBlock(BaseModel):
    """Recurring weekly block (保育園お迎え、就寝、夕食、家族時間、運動 etc.)"""
    id: str = ""
    title: str
    weekday: int  # 0=Mon … 6=Sun
    start_hm: str  # "HH:MM"
    end_hm: str
    category: Category = "family"


class PlanRequest(BaseModel):
    horizon_days: int = 7
    engine: str = "claude"  # AI to use for the plan generation itself


# ─── Storage helpers ────────────────────────────────────────────────────────
def _read_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_backlog() -> list[dict]:
    return _read_json(BACKLOG_PATH, [])


def _load_life_blocks() -> list[dict]:
    return _read_json(LIFE_BLOCKS_PATH, [])


def _next_id() -> str:
    return f"p{int(datetime.now().timestamp() * 1000)}"


# ─── CRUD: backlog ──────────────────────────────────────────────────────────
@router.get("/productivity/backlog")
def list_backlog():
    return {"items": _load_backlog()}


@router.post("/productivity/backlog")
def add_backlog(item: BacklogItem):
    items = _load_backlog()
    new = item.model_dump()
    new["id"] = new.get("id") or _next_id()
    items.append(new)
    _write_json(BACKLOG_PATH, items)
    return new


@router.put("/productivity/backlog/{item_id}")
def update_backlog(item_id: str, item: BacklogItem):
    items = _load_backlog()
    updated = None
    for i, it in enumerate(items):
        if it.get("id") == item_id:
            new_data = item.model_dump()
            new_data["id"] = item_id
            items[i] = new_data
            updated = new_data
            break
    if not updated:
        raise HTTPException(status_code=404, detail="item not found")
    _write_json(BACKLOG_PATH, items)
    return updated


@router.delete("/productivity/backlog/{item_id}")
def delete_backlog(item_id: str):
    items = _load_backlog()
    items = [it for it in items if it.get("id") != item_id]
    _write_json(BACKLOG_PATH, items)
    return {"ok": True}


# ─── CRUD: life blocks ──────────────────────────────────────────────────────
@router.get("/productivity/life-blocks")
def list_life_blocks():
    return {"items": _load_life_blocks()}


@router.post("/productivity/life-blocks")
def add_life_block(block: LifeBlock):
    items = _load_life_blocks()
    new = block.model_dump()
    new["id"] = new.get("id") or _next_id()
    items.append(new)
    _write_json(LIFE_BLOCKS_PATH, items)
    return new


@router.delete("/productivity/life-blocks/{block_id}")
def delete_life_block(block_id: str):
    items = _load_life_blocks()
    items = [it for it in items if it.get("id") != block_id]
    _write_json(LIFE_BLOCKS_PATH, items)
    return {"ok": True}


# ─── Plan generation ────────────────────────────────────────────────────────
@router.post("/productivity/plan")
def generate_plan(req: PlanRequest):
    now = now_jst()
    end = now + timedelta(days=req.horizon_days)

    # Pull Google Calendar fixed events
    cal_events: list[dict] = []
    try:
        from gcal import is_configured, list_events_range
        if is_configured():
            cal_events = list_events_range(
                start_date=now.strftime("%Y-%m-%d"),
                end_date=end.strftime("%Y-%m-%d"),
            )
    except Exception:
        pass

    backlog = [b for b in _load_backlog() if not b.get("done")]
    life_blocks = _load_life_blocks()

    # Build the AI prompt
    cal_text = "\n".join(
        f"- {ev['start_iso'][:16]} 〜 {ev['end_iso'][:16]} {ev['title']}" + (f" @ {ev['location']}" if ev.get("location") else "")
        for ev in cal_events[:60]
    ) or "(Calendar に予定なし)"

    life_text = "\n".join(
        f"- 毎週 {['月','火','水','木','金','土','日'][b['weekday']]} {b['start_hm']}〜{b['end_hm']} {b['title']} [{b['category']}]"
        for b in life_blocks
    ) or "(固定の生活ブロックなし)"

    backlog_text = "\n".join(
        f"- [{b['urgency']}] [{b['category']}] {b['title']} (推定{b['estimated_minutes']}分)"
        + (f"\n  メモ: {b['notes']}" if b.get("notes") else "")
        + (f"\n  ← AI ツール推奨を求める" if b.get("needs_ai") else "")
        for b in backlog
    ) or "(バックログなし)"

    system_prompt = """あなたは志柿のパーソナル生産性コーチ。志柿の状況は:
- 大学教員 + 個人開発（EGAKU AI, crypto-trader, Koach OS, English platform 等）を並走
- 家族あり、保育園のお迎えあり
- ブレイクダンス・アクロバットの再開を目指している
- ク リエイティブな趣味（AI 画像生成、執筆）も持っている
- 複数の生成 AI を併用しながら開発・執筆・研究を並行進行

あなたの仕事:
1. Google Calendar の固定予定 + 毎週繰り返しの生活ブロック（保育園お迎え等）を尊重した上で、空き時間を把握
2. バックログのタスクを、優先度・推定時間・カテゴリのバランスを見ながら配置
3. 全カテゴリ（キャリア/家族/健康/クリエイティブ/休息）に時間を確保する。1つに偏らない
4. 「もうこれ以上は無理」というラインを見える化し、無理な時は減らす提案
5. AI ツール推奨が必要なタスクは、適切な AI（Claude=戦略・分析・長文、GPT=コード・実装、Gemini=長文書類解析・PDF・画像、Grok=代替視点・最新情報、Perplexity=Web検索ベース調査、Venice=制約なし、Groq=爆速軽処理）を選び、プロンプト例を1つ書く

出力フォーマット:
1. 📊 状況分析 (3-5行) — 全体感、無理な配置や偏りの指摘
2. 📅 提案スケジュール (期間内の日ごと、時間ブロック付き)
   - 日付 (曜日):
     - HH:MM-HH:MM タスク名 [カテゴリ絵文字] — 一言メモ
3. 🤖 AI ツール推奨 (needs_ai=true のタスクのみ)
   - タスク名 → 推奨 AI（理由）
     プロンプト例: ...
4. ⚖ バランスチェック — 健康/家族/クリエイティブ/休息の確保状況
5. 🎯 今週捻出できそうな新しい時間 — ブレイクダンス再開、副プロジェクト等への割り当て提案 1-2件

トーン: 簡潔、煽らない、です/ます調、抽象名詞「〜性」は使わない。
"""

    user_msg = f"""今日: {now.strftime('%Y-%m-%d %H:%M (%A)')}
期間: 今日から {req.horizon_days} 日間

## Google Calendar 上の固定予定
{cal_text}

## 毎週繰り返しの生活ブロック
{life_text}

## バックログ (やりたい / やらないといけないこと)
{backlog_text}

上記を踏まえ、提案スケジュールを作成してください。"""

    engine = req.engine if req.engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS.get(engine, DEFAULT_MODELS["claude"])

    try:
        plan = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
            engine=engine,
            model=model,
            max_tokens=4000,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"plan generation failed: {e}")

    return {
        "generated_at": now.isoformat(),
        "horizon_days": req.horizon_days,
        "calendar_events_count": len(cal_events),
        "backlog_count": len(backlog),
        "life_blocks_count": len(life_blocks),
        "engine_used": engine,
        "model_used": model,
        "plan": plan,
    }


@router.get("/productivity/categories")
def list_categories():
    return {
        "categories": [
            {"id": k, "emoji": v[0], "label": v[1]}
            for k, v in CATEGORY_META.items()
        ]
    }
