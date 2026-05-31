"""
マルチプロジェクト把握ダッシュボード。
並行で動いている全プロジェクト (EGAKU / crypto-trader / SpeakSmart 等) を一覧 + 詳細管理。
「今日どれに触る?」を AI が推奨。Alfred 構想の中核。

スキーマ:
{
  "updated_at": "...",
  "projects": [
    {
      "id": "egaku",
      "name": "EGAKU AI",
      "category": "saas",          # saas | research | platform | infra | creative
      "status": "active",          # active | maintenance | paused | archived | planning
      "priority": 5,               # 1-5
      "github_url": "https://github.com/koach08/egaku-ai",
      "live_url": "https://egaku-ai.com",
      "local_path": "~/Desktop/アプリ開発プロジェクト/ai-studio",
      "memory_ref": "egaku_ai.md",
      "one_liner": "AI 画像/動画生成 SaaS",
      "next_action": "メンテ週間 Day 1-7: 60+ ルート動作確認",
      "last_touched": "2026-05-26",
      "notes": "..."
    }
  ]
}
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import DATA_DIR, now_jst, timestamp_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

PROJECTS_FILE = DATA_DIR / "projects.json"


class Project(BaseModel):
    id: str
    name: str
    category: str = "saas"
    status: str = "active"
    priority: int = 3
    github_url: str = ""
    live_url: str = ""
    local_path: str = ""
    memory_ref: str = ""
    one_liner: str = ""
    next_action: str = ""
    last_touched: str = ""
    notes: str = ""
    # Auto-synced from local git (optional)
    last_commit_sha: str = ""
    last_commit_message: str = ""
    last_commit_date: str = ""
    last_commit_author: str = ""
    uncommitted_changes: int = 0  # working tree dirty file count
    sync_source: str = ""  # "git" | "claude-code-hook" | "manual"
    sync_at: str = ""


def _read() -> dict:
    if not PROJECTS_FILE.exists():
        return {"updated_at": None, "projects": []}
    try:
        return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"updated_at": None, "projects": []}


def _write(data: dict):
    data["updated_at"] = timestamp_jst()
    PROJECTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


SEED_PROJECTS: list[dict] = [
    {
        "id": "egaku",
        "name": "EGAKU AI",
        "category": "saas",
        "status": "active",
        "priority": 5,
        "github_url": "https://github.com/koach08/egaku-ai",
        "live_url": "https://egaku-ai.com",
        "local_path": "~/Desktop/アプリ開発プロジェクト/ai-studio",
        "memory_ref": "egaku_ai.md",
        "one_liner": "AI 画像/動画生成 SaaS (149 登録、有料転換中)",
        "next_action": "メンテ週間: 60+ dashboard ルートの動作確認 + 決済チャネル拡張",
        "last_touched": "2026-05-26",
        "notes": "Next.js + FastAPI + Supabase + Stripe + NOWPayments",
    },
    {
        "id": "crypto-trader",
        "name": "crypto-trader",
        "category": "saas",
        "status": "active",
        "priority": 4,
        "github_url": "https://github.com/koach08/crypto-trader",
        "live_url": "",
        "local_path": "~/Desktop/アプリ開発プロジェクト/crypto-trader",
        "memory_ref": "crypto_trader_app.md",
        "one_liner": "仮想通貨 AI 自動売買 (Railway 24/7 稼働、ETH/XRP DCA)",
        "next_action": "Phase 2: 自己改善ループ。¥77K 観察中、黒字化後追加入金",
        "last_touched": "2026-05-29",
        "notes": "BitFlyer API、毎日少額利益優先",
    },
    {
        "id": "koach-os",
        "name": "Koach OS",
        "category": "platform",
        "status": "active",
        "priority": 5,
        "github_url": "https://github.com/koach08/koach-os-app",
        "live_url": "https://koach-os.vercel.app",
        "local_path": "/tmp/koach-os-app",
        "memory_ref": "koach_os_state_20260523.md",
        "one_liner": "Personal AI OS (Alfred 構想、本アプリ)",
        "next_action": "Phase 8: マルチプロジェクト把握 / 自動 AI モデル追従",
        "last_touched": "2026-05-31",
        "notes": "Next.js + FastAPI、Vercel 手動デプロイ",
    },
    {
        "id": "speaksmart",
        "name": "SpeakSmart (商用版)",
        "category": "saas",
        "status": "active",
        "priority": 4,
        "github_url": "https://github.com/koach08/english-platform-commercial",
        "live_url": "https://speaksmart.jp",
        "local_path": "~/Desktop/アプリ開発プロジェクト/english-platform-commercial",
        "memory_ref": "speaksmart.md",
        "one_liner": "英語学習プラットフォーム 商用版",
        "next_action": "学習の質・上達を中心としたマーケ展開",
        "last_touched": "",
        "notes": "5年計画: 北大発スタートアップ移行構想",
    },
    {
        "id": "english-platform-univ",
        "name": "英語プラットフォーム (大学版)",
        "category": "platform",
        "status": "active",
        "priority": 3,
        "github_url": "https://github.com/koach08/english-platform-next",
        "live_url": "https://english-platform-next.vercel.app",
        "local_path": "~/Desktop/アプリ開発プロジェクト/english-platform-next",
        "memory_ref": "english_platform_university.md",
        "one_liner": "北大 英語 II 用プラットフォーム",
        "next_action": "",
        "last_touched": "",
        "notes": "大学版と Language x AI WP は分離運用",
    },
    {
        "id": "english-assessment",
        "name": "english_assessment_v2",
        "category": "research",
        "status": "active",
        "priority": 3,
        "github_url": "https://github.com/koach08/english-assessment-v2",
        "live_url": "",
        "local_path": "~/Desktop/アプリ開発プロジェクト/english_assessment_v2",
        "memory_ref": "",
        "one_liner": "発音評価パイプライン (Notion → Azure Speech)",
        "next_action": "",
        "last_touched": "",
        "notes": "iCloud に研究データ",
    },
    {
        "id": "code-harness",
        "name": "Code Harness v2",
        "category": "platform",
        "status": "active",
        "priority": 3,
        "github_url": "https://github.com/koach08/code-harness",
        "live_url": "",
        "local_path": "~/Desktop/アプリ開発プロジェクト/code-harness",
        "memory_ref": "code_harness_v2.md",
        "one_liner": "Personal AI OS (Electron 版、koach-os と統合候補)",
        "next_action": "Phase 1 (AI Hub)",
        "last_touched": "2026-05-02",
        "notes": "Electron + Vite + React",
    },
    {
        "id": "investment-app",
        "name": "investment-app",
        "category": "saas",
        "status": "active",
        "priority": 3,
        "github_url": "",
        "live_url": "",
        "local_path": "~/investment-app",
        "memory_ref": "investment_app.md",
        "one_liner": "AI 投資分析 (Next.js + MF Playwright スクレイピング)",
        "next_action": "koach-os と KPI 連携",
        "last_touched": "",
        "notes": "port 3003",
    },
    {
        "id": "persian-learning",
        "name": "ペルシア語学習",
        "category": "saas",
        "status": "active",
        "priority": 2,
        "github_url": "https://github.com/koach08/persian-learning",
        "live_url": "",
        "local_path": "",
        "memory_ref": "persian_learning_app.md",
        "one_liner": "Next.js + Capacitor (iOS) + Azure Speech",
        "next_action": "iOS App Store 審査準備",
        "last_touched": "2026-04-19",
        "notes": "GitHub のみ (ローカルなし)",
    },
    {
        "id": "eduplanner",
        "name": "EduPlanner",
        "category": "saas",
        "status": "maintenance",
        "priority": 2,
        "github_url": "https://github.com/koach08/eduplanner",
        "live_url": "https://nipponbusiness.gumroad.com",
        "local_path": "",
        "memory_ref": "eduplanner.md",
        "one_liner": "授業計画ツール (Gumroad 公開済み、MAS 審査待ち)",
        "next_action": "Gumroad 売上モニタ、MAS 進捗",
        "last_touched": "",
        "notes": "Next.js + Electron + Prisma + SQLite",
    },
    {
        "id": "uniagent",
        "name": "UniAgent (大学事務エージェント)",
        "category": "saas",
        "status": "paused",
        "priority": 2,
        "github_url": "https://github.com/koach08/uni-agent-app",
        "live_url": "",
        "local_path": "",
        "memory_ref": "univ_admin_agent.md",
        "one_liner": "Next.js + Claude tool_use",
        "next_action": "Phase 3 完了。次フェーズ未定",
        "last_touched": "2026-04-05",
        "notes": "",
    },
    {
        "id": "alfred-batman",
        "name": "Alfred-batman (Koach OS v2 prototype)",
        "category": "platform",
        "status": "paused",
        "priority": 2,
        "github_url": "https://github.com/koach08/alfred-batman",
        "live_url": "",
        "local_path": "",
        "memory_ref": "alfred_batman.md",
        "one_liner": "Streamlit プロトタイプ。koach-os に統合済み",
        "next_action": "アーカイブ判断",
        "last_touched": "",
        "notes": "Streamlit + Claude + GPT + ChromaDB",
    },
    {
        "id": "ai-diffusion",
        "name": "AI-diffusion",
        "category": "creative",
        "status": "active",
        "priority": 2,
        "github_url": "https://github.com/koach08/ai-diffusion-studio",
        "live_url": "https://comfyui.egaku-ai.com",
        "local_path": "",
        "memory_ref": "",
        "one_liner": "Gradio + ComfyUI、vast.ai 共有バックエンド",
        "next_action": "AnimateDiff、TTS Kokoro 統合",
        "last_touched": "",
        "notes": "EGAKU と GPU 共有",
    },
    {
        "id": "agentsift",
        "name": "AgentSift",
        "category": "saas",
        "status": "planning",
        "priority": 2,
        "github_url": "https://github.com/koach08/agentsift",
        "live_url": "",
        "local_path": "",
        "memory_ref": "agentsift.md",
        "one_liner": "Python CLI v0.1.0",
        "next_action": "GitHub 公開",
        "last_touched": "",
        "notes": "",
    },
    {
        "id": "souji",
        "name": "Souji",
        "category": "saas",
        "status": "planning",
        "priority": 1,
        "github_url": "https://github.com/koach08/souji",
        "live_url": "",
        "local_path": "",
        "memory_ref": "souji_app.md",
        "one_liner": "Tauri 2.0 + React",
        "next_action": "",
        "last_touched": "",
        "notes": "",
    },
    {
        "id": "language-smartlearning-wp",
        "name": "Language x AI Lab WP",
        "category": "platform",
        "status": "active",
        "priority": 3,
        "github_url": "",
        "live_url": "https://www.language-smartlearning.com",
        "local_path": "",
        "memory_ref": "",
        "one_liner": "WordPress (ロリポップ) + Astra + Yoast",
        "next_action": "AI 情報の歩き方カテゴリ拡充",
        "last_touched": "",
        "notes": "大学版と分離",
    },
    {
        "id": "kakenhi-2026",
        "name": "科研費基盤C 再申請",
        "category": "research",
        "status": "active",
        "priority": 4,
        "github_url": "",
        "live_url": "",
        "local_path": "",
        "memory_ref": "research_portfolio_2026.md",
        "one_liner": "2026 年 8 月末再申請 (前回 B 判定不採択)",
        "next_action": "B 判定改善ポイント反映、申請書ドラフト",
        "last_touched": "",
        "notes": "",
    },
    {
        "id": "english2-ta",
        "name": "英語 II TA 係業務 (2026)",
        "category": "research",
        "status": "active",
        "priority": 3,
        "github_url": "",
        "live_url": "",
        "local_path": "",
        "memory_ref": "english2_ta_management.md",
        "one_liner": "TA 係 (北大)",
        "next_action": "",
        "last_touched": "",
        "notes": "iCloud 英語IITA関係",
    },
]


@router.get("/projects")
def list_projects():
    data = _read()
    projects = data.get("projects", [])
    by_status: dict[str, list] = {}
    by_category: dict[str, list] = {}
    for p in projects:
        by_status.setdefault(p.get("status", "active"), []).append(p)
        by_category.setdefault(p.get("category", "saas"), []).append(p)
    return {
        "updated_at": data.get("updated_at"),
        "projects": projects,
        "by_status": by_status,
        "by_category": by_category,
        "count": len(projects),
    }


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    data = _read()
    for p in data.get("projects", []):
        if p.get("id") == project_id:
            return p
    raise HTTPException(status_code=404, detail=f"project {project_id} not found")


@router.post("/projects")
def upsert_project(p: Project):
    data = _read()
    projects = data.get("projects", [])
    existing = next((x for x in projects if x.get("id") == p.id), None)
    if existing:
        existing.update(p.model_dump())
    else:
        projects.append(p.model_dump())
    data["projects"] = projects
    _write(data)
    return p.model_dump()


class ProjectPatch(BaseModel):
    name: str | None = None
    category: str | None = None
    status: str | None = None
    priority: int | None = None
    github_url: str | None = None
    live_url: str | None = None
    local_path: str | None = None
    memory_ref: str | None = None
    one_liner: str | None = None
    next_action: str | None = None
    last_touched: str | None = None
    notes: str | None = None


@router.patch("/projects/{project_id}")
def patch_project(project_id: str, patch: ProjectPatch):
    data = _read()
    projects = data.get("projects", [])
    for p in projects:
        if p.get("id") == project_id:
            for k, v in patch.model_dump(exclude_none=True).items():
                p[k] = v
            data["projects"] = projects
            _write(data)
            return p
    raise HTTPException(status_code=404, detail=f"project {project_id} not found")


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    data = _read()
    before = len(data.get("projects", []))
    data["projects"] = [p for p in data.get("projects", []) if p.get("id") != project_id]
    if len(data["projects"]) == before:
        raise HTTPException(status_code=404, detail=f"project {project_id} not found")
    _write(data)
    return {"ok": True, "deleted": project_id}


@router.post("/projects/touched/{project_id}")
def mark_touched(project_id: str):
    """触ったら last_touched を今日に更新"""
    data = _read()
    today = now_jst().strftime("%Y-%m-%d")
    for p in data.get("projects", []):
        if p.get("id") == project_id:
            p["last_touched"] = today
            _write(data)
            return p
    raise HTTPException(status_code=404, detail=f"project {project_id} not found")


class SyncItem(BaseModel):
    """ローカル / Claude Code から送る git ベースの最新情報"""
    id: str
    last_commit_sha: str = ""
    last_commit_message: str = ""
    last_commit_date: str = ""  # ISO 8601
    last_commit_author: str = ""
    uncommitted_changes: int = 0
    source: str = "git"  # "git" | "claude-code-hook" | "manual"


class SyncBatch(BaseModel):
    items: list[SyncItem]


@router.post("/projects/sync")
def sync_projects(batch: SyncBatch):
    """ローカル git の最新コミット情報を一括反映。
    last_touched は last_commit_date の日付部分で上書き (より直近の場合のみ)。
    project が存在しない id は無視。
    """
    data = _read()
    projects = data.get("projects", [])
    by_id = {p.get("id"): p for p in projects}
    updated = []
    skipped = []
    now_iso = now_jst().isoformat()

    for item in batch.items:
        p = by_id.get(item.id)
        if not p:
            skipped.append(item.id)
            continue

        if item.last_commit_sha:
            p["last_commit_sha"] = item.last_commit_sha
        if item.last_commit_message:
            p["last_commit_message"] = item.last_commit_message
        if item.last_commit_date:
            p["last_commit_date"] = item.last_commit_date
            # last_touched は新しい commit_date の方が大きい時のみ更新
            commit_day = item.last_commit_date[:10]
            if commit_day and commit_day > (p.get("last_touched") or ""):
                p["last_touched"] = commit_day
        if item.last_commit_author:
            p["last_commit_author"] = item.last_commit_author
        p["uncommitted_changes"] = item.uncommitted_changes
        p["sync_source"] = item.source
        p["sync_at"] = now_iso
        updated.append(item.id)

    data["projects"] = projects
    _write(data)
    return {
        "ok": True,
        "updated": updated,
        "skipped_unknown": skipped,
        "count": len(updated),
    }


@router.post("/projects/seed")
def seed_projects(force: bool = False):
    """memory ファイル群を元にした初期 seed を投入。force=true で全上書き、false で merge (id 衝突は既存優先)"""
    data = _read()
    existing = data.get("projects", [])
    existing_ids = {p.get("id") for p in existing}
    if force:
        data["projects"] = SEED_PROJECTS.copy()
        _write(data)
        return {"ok": True, "mode": "force", "count": len(SEED_PROJECTS)}
    added = 0
    for sp in SEED_PROJECTS:
        if sp["id"] not in existing_ids:
            existing.append(sp)
            added += 1
    data["projects"] = existing
    _write(data)
    return {"ok": True, "mode": "merge", "added": added, "total": len(existing)}


class RecommendReq(BaseModel):
    mood: str = ""  # 「疲れてる」「集中したい」「ライト作業しかしたくない」など
    available_hours: float = 2.0
    context: str = ""  # 「今日は午後2時間だけ」「家族の予定で夜は無理」など
    engine: str = "claude"


@router.post("/projects/recommend")
def recommend(req: RecommendReq):
    """今日どのプロジェクトに触るべきかを AI 推奨"""
    data = _read()
    projects = data.get("projects", [])
    if not projects:
        raise HTTPException(status_code=400, detail="プロジェクトが seed されていません。POST /projects/seed を先に")

    # AI に渡す簡易フォーマット
    active = [p for p in projects if p.get("status") in ("active", "maintenance")]
    rows = []
    for p in active:
        rows.append(
            f"- [{p['id']}] {p['name']} (priority={p.get('priority',3)}, status={p.get('status')}, last_touched={p.get('last_touched') or '未記録'})\n"
            f"    {p.get('one_liner','')}\n"
            f"    次アクション: {p.get('next_action') or '(未設定)'}"
        )
    projects_text = "\n".join(rows)

    system_prompt = """あなたは志柿のプロジェクト総合秘書 (Alfred)。
複数プロジェクトを並行運用している志柿に対し、今日触るべきプロジェクトを 1-2 個推奨する。

## 判断基準
1. **priority** (5 が最高) を最優先
2. **last_touched** が古いものは「冷え始め」のリスク
3. **next_action** が具体的なものを優先 (動かしやすい)
4. ユーザーの mood / available_hours / context に合わせる
   - 疲れている → 軽い作業 / メンテ系
   - 集中できる → priority 5 の重い設計
   - 時間が短い → 1 つに絞る
5. EGAKU / crypto-trader / koach-os は中核。優先度高めに見る
6. 複数候補を挙げて迷わせるより、1つを強く推す

## 出力 (MD)

### 🎯 今日触るべきプロジェクト
**[id] プロジェクト名** — 一行で理由

### 🚀 今日の具体的アクション (60-90 分で動けるサイズに分解)
1. ...
2. ...
3. ...

### ⚠ 他に気になっているもの (1個だけ言及、深追いしない)
- ...

### 💬 一言
- 簡潔に。煽らない、励まさない、抽象名詞「〜性」NG"""

    today = now_jst().strftime("%Y-%m-%d (%A)")
    user_msg = f"""今: {today}
気分: {req.mood or "(指定なし)"}
使える時間: {req.available_hours} 時間
コンテキスト: {req.context or "(なし)"}

## アクティブプロジェクト一覧
{projects_text}

上記から「今日触るべきプロジェクト 1 つ」と「具体アクション」を出してください。"""

    engine = req.engine if req.engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS[engine]

    try:
        out = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
            engine=engine,
            model=model,
            max_tokens=1500,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"recommend failed: {e}")

    return {
        "generated_at": now_jst().isoformat(),
        "engine_used": engine,
        "model_used": model,
        "recommendation": out,
        "considered": [{"id": p["id"], "name": p["name"], "priority": p.get("priority", 3)} for p in active],
    }
