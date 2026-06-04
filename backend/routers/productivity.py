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
    done_at: str | None = None
    defer_until: str | None = None  # YYYY-MM-DD; その日まで Daily Brief から隠す
    due_date: str | None = None  # YYYY-MM-DD; 締切


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


class DoneToggle(BaseModel):
    done: bool = True


@router.post("/productivity/backlog/{item_id}/done")
def toggle_done(item_id: str, body: DoneToggle):
    items = _load_backlog()
    found = None
    for it in items:
        if it.get("id") == item_id:
            it["done"] = body.done
            it["done_at"] = now_jst().isoformat() if body.done else None
            found = it
            break
    if not found:
        raise HTTPException(404, "not found")
    _write_json(BACKLOG_PATH, items)
    return found


class DeferReq(BaseModel):
    days: int | None = None  # +N 日後
    date: str | None = None  # 直接指定 YYYY-MM-DD; days より優先
    clear: bool = False  # True で defer_until をクリア


@router.post("/productivity/backlog/{item_id}/defer")
def defer_backlog(item_id: str, body: DeferReq):
    items = _load_backlog()
    found = None
    for it in items:
        if it.get("id") == item_id:
            if body.clear:
                it["defer_until"] = None
            elif body.date:
                it["defer_until"] = body.date
            elif body.days is not None:
                target = now_jst().date() + timedelta(days=max(0, body.days))
                it["defer_until"] = target.isoformat()
            else:
                raise HTTPException(400, "days か date か clear が必要")
            found = it
            break
    if not found:
        raise HTTPException(404, "not found")
    _write_json(BACKLOG_PATH, items)
    return found


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


class LifeBlockBulk(BaseModel):
    """複数曜日にまとめて life-block を登録 (保育園送迎=月-金 等)"""
    title: str
    weekdays: list[int]  # [0,1,2,3,4] = 月-金
    start_hm: str
    end_hm: str
    category: Category = "family"


@router.post("/productivity/life-blocks/bulk")
def add_life_blocks_bulk(req: LifeBlockBulk):
    if not req.weekdays:
        raise HTTPException(status_code=400, detail="weekdays が空です")
    items = _load_life_blocks()
    created = []
    base_ts = int(datetime.now().timestamp() * 1000)
    for i, wd in enumerate(req.weekdays):
        if wd < 0 or wd > 6:
            continue
        new = {
            "id": f"p{base_ts + i}",
            "title": req.title,
            "weekday": wd,
            "start_hm": req.start_hm,
            "end_hm": req.end_hm,
            "category": req.category,
        }
        items.append(new)
        created.append(new)
    _write_json(LIFE_BLOCKS_PATH, items)
    return {"created": created, "count": len(created)}


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


class PlannedBlock(BaseModel):
    """A single time-block to write into Google Calendar from Coach."""
    title: str
    start_iso: str
    end_iso: str
    category: Category = "other"
    description: str = ""


class CommitPlanRequest(BaseModel):
    blocks: list[PlannedBlock]


@router.post("/productivity/commit-plan")
def commit_plan(req: CommitPlanRequest):
    """Write a list of Coach-suggested time blocks into Google Calendar (event_type=default reminder)."""
    try:
        from gcal import is_configured, create_event
    except Exception:
        raise HTTPException(status_code=500, detail="gcal module unavailable")
    if not is_configured():
        raise HTTPException(status_code=400, detail="Google integration not configured")

    results: list[dict] = []
    for blk in req.blocks:
        try:
            ev = create_event(
                title=f"{CATEGORY_META.get(blk.category, ('✨',''))[0]} {blk.title}",
                start_iso=blk.start_iso,
                end_iso=blk.end_iso,
                description=blk.description or f"[Koach Coach] category={blk.category}",
                event_type="default",
            )
            results.append({"ok": True, "id": ev.get("id", ""), "html_link": ev.get("htmlLink", "")})
        except Exception as e:
            results.append({"ok": False, "error": str(e), "title": blk.title})
    return {"count": len(results), "results": results}


@router.post("/productivity/parse-plan")
def parse_plan_to_blocks(payload: dict):
    """Use AI to convert a free-form Coach plan text into structured blocks (for the commit UI)."""
    plan_text = payload.get("plan", "")
    if not plan_text:
        raise HTTPException(status_code=400, detail="plan text required")

    today_str = now_jst().strftime("%Y-%m-%d (%A)")
    system_prompt = f"""You convert a Japanese productivity plan (with date sections and HH:MM-HH:MM time blocks) into structured JSON.

TODAY IS: {today_str}

Read the plan and output ONLY a JSON array of time blocks. Each block:
{{"title": "...", "start_iso": "YYYY-MM-DDTHH:MM:00+09:00", "end_iso": "...", "category": "career|research|creative|family|health|learning|side_project|admin|rest|other", "description": ""}}

Rules:
- Skip blocks that are 既存の Calendar イベント（試験・固定予定など）— extract only NEW proposed blocks
- Skip vague entries (例: 「自由時間」「家族時間」without specific task)
- Skip "就寝準備" or pure rest blocks unless they have a specific actionable label
- Keep tasks with clear titles (例: "科研費基盤C再申請の構成案", "ブレイクダンス練習")
- Infer the date from section headers like "5/24 (日)"
- Use Asia/Tokyo (+09:00) timezone
- If a section has no specific HH:MM range, skip that entry

Output: JSON array only, no markdown."""

    try:
        raw = call_ai(
            messages=[{"role": "user", "content": f"以下の計画から時間ブロックを抽出してください:\n\n{plan_text}"}],
            system=system_prompt,
            engine="gemini",
            model=DEFAULT_MODELS.get("gemini", "gemini-2.0-flash-exp"),
            max_tokens=4000,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"parse failed: {e}")

    # Reuse the same JSON repair from gmail_calendar
    import re as _re
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = _re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = _re.sub(r"\s*```$", "", cleaned)
    if not cleaned.startswith("["):
        first = cleaned.find("[")
        if first != -1:
            cleaned = cleaned[first:]
    try:
        blocks = json.loads(cleaned)
    except Exception:
        try:
            from backend.routers.gmail_calendar import _repair_truncated_json_array
            repaired = _repair_truncated_json_array(cleaned)
            blocks = json.loads(repaired) if repaired else []
        except Exception:
            blocks = []
    if not isinstance(blocks, list):
        blocks = []

    # Normalize
    out = []
    for b in blocks:
        if not isinstance(b, dict) or not b.get("title") or not b.get("start_iso"):
            continue
        out.append({
            "title": str(b.get("title", ""))[:200],
            "start_iso": str(b.get("start_iso", "")),
            "end_iso": str(b.get("end_iso", "")) or str(b.get("start_iso", "")),
            "category": b.get("category", "other"),
            "description": str(b.get("description", ""))[:300],
        })
    return {"blocks": out}


@router.get("/productivity/categories")
def list_categories():
    return {
        "categories": [
            {"id": k, "emoji": v[0], "label": v[1]}
            for k, v in CATEGORY_META.items()
        ]
    }


class BacklogHermesReq(BaseModel):
    project_id: str = ""  # 関連プロジェクトがあれば。空なら project context は付けない
    extra_task: str = ""  # ユーザーが追加で書きたいこと


@router.post("/productivity/backlog/{item_id}/hermes-handoff")
def backlog_hermes_handoff(item_id: str, req: BacklogHermesReq):
    """バックログ項目を Hermes Desktop 用のプロンプトに整形"""
    backlog = _load_backlog()
    item = next((b for b in backlog if b.get("id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="backlog item not found")

    cat = item.get("category", "other")
    emoji, cat_label = CATEGORY_META.get(cat, ("✨", "その他"))

    parts: list[str] = []
    parts.append(f"# Koach OS → Hermes ハンドオフ: {item.get('title')}")
    parts.append("")
    parts.append("## あなたへの依頼")
    if req.extra_task.strip():
        parts.append(req.extra_task.strip())
        parts.append("")
        parts.append(f"### 元のバックログ項目: {item.get('title')}")
    else:
        parts.append(item.get('title', ''))
    parts.append("")

    parts.append("## バックログメタ情報")
    parts.append(f"- **カテゴリ**: {emoji} {cat_label}")
    parts.append(f"- **見積もり**: {item.get('estimated_minutes', 60)} 分")
    parts.append(f"- **緊急度**: {item.get('urgency', 'medium')}")
    if item.get("due_date"):
        parts.append(f"- **締切**: {item['due_date']}")
    if item.get("notes"):
        parts.append("")
        parts.append("### 元のメモ")
        parts.append(item["notes"])
    parts.append("")

    # プロジェクト連携
    if req.project_id:
        try:
            from routers.projects import _read as _read_projects
            pdata = _read_projects()
            p = next((x for x in pdata.get("projects", []) if x.get("id") == req.project_id), None)
            if p:
                parts.append(f"## 関連プロジェクト: {p.get('name')}")
                if p.get("one_liner"):
                    parts.append(f"- {p['one_liner']}")
                if p.get("github_url"):
                    parts.append(f"- GitHub: {p['github_url']}")
                if p.get("local_path"):
                    parts.append(f"- ローカル: `{p['local_path']}`")
                if p.get("next_action"):
                    parts.append(f"- next_action: {p['next_action']}")
                recent = p.get("recent_commits") or []
                if recent:
                    parts.append("")
                    parts.append("### 関連プロジェクトの最近のコミット (上 5 件)")
                    for c in recent[:5]:
                        parts.append(f"- `{c.get('date','?')[:10]} {c.get('sha','')[:7]}` {c.get('message','')}")
                parts.append("")
        except Exception:
            pass

    parts.append("---")
    parts.append("## あなたが満たすべき条件")
    parts.append("- 完了時、何をやったか + 次の手 (確認 / テスト / 次のタスク) を提示")
    parts.append("- 質問は最大 1 個、それ以外は仮定して進めてよい")
    parts.append("")
    parts.append(f"_Generated by Koach OS at {now_jst().isoformat()}_")

    prompt = "\n".join(parts)
    return {
        "item_id": item_id,
        "title": item.get("title"),
        "prompt": prompt,
        "char_count": len(prompt),
        "generated_at": now_jst().isoformat(),
    }
