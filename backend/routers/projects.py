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
CANDIDATES_FILE = DATA_DIR / "project_candidates.json"
REJECTED_FILE = DATA_DIR / "project_candidates_rejected.json"


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
    # Project docs (memory + README + recent commits) — advise 機能の source
    docs: list[dict] = []  # [{name, content, source}]
    recent_commits: list[dict] = []  # [{sha, message, date}]
    docs_synced_at: str = ""


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


def _read_candidates() -> list[dict]:
    if not CANDIDATES_FILE.exists():
        return []
    try:
        return json.loads(CANDIDATES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_candidates(items: list[dict]):
    CANDIDATES_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_rejected() -> list[str]:
    """却下済み candidate id のリスト (再提案を防ぐ)"""
    if not REJECTED_FILE.exists():
        return []
    try:
        return json.loads(REJECTED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write_rejected(ids: list[str]):
    REJECTED_FILE.write_text(json.dumps(ids, ensure_ascii=False, indent=2), encoding="utf-8")


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


@router.get("/projects/candidates")
def list_candidates_route():
    """※ {project_id} catch-all より前に置く必要あり (FastAPI は登録順マッチ)"""
    candidates = _read_candidates()
    by_source: dict[str, list] = {}
    for c in candidates:
        by_source.setdefault(c.get("source", "?"), []).append(c)
    return {
        "candidates": candidates,
        "by_source": by_source,
        "count": len(candidates),
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


class DocItem(BaseModel):
    name: str  # 表示用 (例: "README.md", "memory: egaku_ai.md")
    content: str
    source: str = ""  # "memory" | "readme" | "claude-md" | other


class CommitInfo(BaseModel):
    sha: str = ""
    message: str = ""
    date: str = ""


class SyncItem(BaseModel):
    """ローカル / Claude Code から送る git ベースの最新情報"""
    id: str
    last_commit_sha: str = ""
    last_commit_message: str = ""
    last_commit_date: str = ""  # ISO 8601
    last_commit_author: str = ""
    uncommitted_changes: int = 0
    source: str = "git"  # "git" | "claude-code-hook" | "manual"
    # Optional: 資料も同送できる (advise 用)
    docs: list[DocItem] = []
    recent_commits: list[CommitInfo] = []


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
        if item.docs:
            p["docs"] = [d.model_dump() for d in item.docs]
            p["docs_synced_at"] = now_iso
        if item.recent_commits:
            p["recent_commits"] = [c.model_dump() for c in item.recent_commits]
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


# ─── Discovery: 未登録プロジェクト候補の提案 ──────────────────────────────
import re
import hashlib


def _candidate_id(source: str, key: str) -> str:
    """source + key からハッシュで安定 ID 生成"""
    h = hashlib.md5(f"{source}::{key}".encode()).hexdigest()[:12]
    return f"cand_{h}"


def _already_known(candidate: dict, projects: list[dict]) -> bool:
    """既登録 project と被るか判定 (github_url / local_path / name の lower 一致)"""
    g = (candidate.get("github_url") or "").lower().rstrip("/").rstrip(".git")
    l = (candidate.get("local_path") or "").lower()
    n = (candidate.get("name") or "").lower()
    for p in projects:
        pg = (p.get("github_url") or "").lower().rstrip("/").rstrip(".git")
        pl = (p.get("local_path") or "").lower()
        pn = (p.get("name") or "").lower()
        if g and pg and g == pg:
            return True
        if l and pl and l == pl:
            return True
        if n and pn and n == pn:
            return True
    return False


class LocalRepoCandidate(BaseModel):
    """ローカルスクリプトから渡されるディレクトリスキャン結果"""
    local_path: str
    name: str  # ディレクトリ名等
    github_url: str = ""
    last_commit_date: str = ""
    last_commit_message: str = ""
    file_count: int = 0
    has_package_json: bool = False
    has_pyproject: bool = False
    has_cargo_toml: bool = False
    notes: str = ""


class LocalDiscoveryBatch(BaseModel):
    items: list[LocalRepoCandidate]


@router.post("/projects/discover/local")
def discover_local(batch: LocalDiscoveryBatch):
    """ローカルスクリプトが ~/Desktop 配下を scan した結果を受けて候補化。
    既登録 / 却下済み と被るものは除外。
    """
    data = _read()
    projects = data.get("projects", [])
    existing_candidates = _read_candidates()
    rejected = set(_read_rejected())
    existing_keys = {c.get("id") for c in existing_candidates}

    new_candidates = []
    now_iso = now_jst().isoformat()
    for it in batch.items:
        cid = _candidate_id("local", it.local_path or it.name)
        if cid in rejected:
            continue
        if cid in existing_keys:
            # 既候補は last_commit_date 等を更新
            for c in existing_candidates:
                if c.get("id") == cid:
                    c.update({
                        "last_commit_date": it.last_commit_date,
                        "last_commit_message": it.last_commit_message,
                        "discovered_at": c.get("discovered_at", now_iso),
                        "updated_at": now_iso,
                    })
                    break
            continue
        candidate = it.model_dump()
        candidate["github_url"] = it.github_url
        if _already_known(candidate, projects):
            continue
        new_candidates.append({
            "id": cid,
            "source": "local",
            "name": it.name,
            "local_path": it.local_path,
            "github_url": it.github_url,
            "last_commit_date": it.last_commit_date,
            "last_commit_message": it.last_commit_message,
            "file_count": it.file_count,
            "stack_hint": _stack_hint(it),
            "notes": it.notes,
            "discovered_at": now_iso,
            "updated_at": now_iso,
        })

    if new_candidates:
        existing_candidates.extend(new_candidates)
    _write_candidates(existing_candidates)
    return {
        "ok": True,
        "added": len(new_candidates),
        "total_candidates": len(existing_candidates),
    }


def _stack_hint(it: LocalRepoCandidate) -> str:
    """簡易スタック推定"""
    hints = []
    if it.has_package_json:
        hints.append("Node.js")
    if it.has_pyproject:
        hints.append("Python")
    if it.has_cargo_toml:
        hints.append("Rust")
    return " / ".join(hints) or "unknown"


@router.post("/projects/discover/gmail")
def discover_gmail(days: int = 30, slot: int = 1):
    """Gmail を scan して GitHub / Vercel / Railway / Stripe 等の通知から
    未登録プロジェクト/サービスを候補化。
    """
    try:
        from gcal import list_recent_emails
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"gcal import failed: {e}")

    try:
        emails = list_recent_emails(days=days, max_results=200, slot=slot)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gmail fetch failed: {e}")

    data = _read()
    projects = data.get("projects", [])
    existing_candidates = _read_candidates()
    rejected = set(_read_rejected())
    existing_keys = {c.get("id") for c in existing_candidates}

    new_candidates = []
    now_iso = now_jst().isoformat()

    # シンプルなパターンマッチング
    SOURCES = [
        # (sender pattern, name extraction regex, service label)
        (r"notifications@github\.com", r"\[([^\]]+/[^\]]+)\]", "github"),
        (r"@vercel\.com", r"Project\s+\"?([a-zA-Z0-9_-]+)\"?", "vercel"),
        (r"@railway\.(app|com)", r"service\s+([a-zA-Z0-9_-]+)", "railway"),
        (r"@stripe\.com", r"product\s+\"?([^\"]+)\"?", "stripe"),
        (r"@netlify\.com", r"site\s+([a-zA-Z0-9_-]+)", "netlify"),
        (r"@supabase\.(io|com)", r"project\s+([a-zA-Z0-9_-]+)", "supabase"),
    ]

    seen_in_run = set()
    for em in emails:
        sender = em.get("from", "")
        subject = em.get("subject", "")
        snippet = em.get("snippet", "")
        text = subject + " " + snippet

        for sender_pat, extract_pat, label in SOURCES:
            if not re.search(sender_pat, sender, re.IGNORECASE):
                continue
            m = re.search(extract_pat, text, re.IGNORECASE)
            if not m:
                continue
            name = m.group(1).strip()
            if len(name) < 2 or len(name) > 80:
                continue
            cid = _candidate_id(f"gmail-{label}", name.lower())
            if cid in rejected or cid in existing_keys or cid in seen_in_run:
                continue
            seen_in_run.add(cid)

            candidate = {"name": name, "github_url": ""}
            if label == "github":
                candidate["github_url"] = f"https://github.com/{name}"
            if _already_known(candidate, projects):
                continue

            new_candidates.append({
                "id": cid,
                "source": f"gmail/{label}",
                "name": name,
                "local_path": "",
                "github_url": candidate.get("github_url", ""),
                "last_email_subject": subject[:160],
                "last_email_from": sender[:80],
                "last_email_date": em.get("date", ""),
                "discovered_at": now_iso,
                "updated_at": now_iso,
            })
            break  # 1メール 1候補

    existing_candidates.extend(new_candidates)
    _write_candidates(existing_candidates)
    return {
        "ok": True,
        "added": len(new_candidates),
        "total_candidates": len(existing_candidates),
        "scanned_emails": len(emails),
    }


class ApproveReq(BaseModel):
    """候補を承認する時に追加で渡せる情報 (デフォルトは候補から推定)"""
    id: str = ""  # project_id として使う slug (省略時は candidate の name から自動生成)
    category: str = "saas"
    status: str = "active"
    priority: int = 3
    one_liner: str = ""
    next_action: str = ""


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9-]+", "-", name.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:40] or "project"


@router.post("/projects/candidates/{candidate_id}/approve")
def approve_candidate(candidate_id: str, req: ApproveReq):
    candidates = _read_candidates()
    cand = next((c for c in candidates if c.get("id") == candidate_id), None)
    if not cand:
        raise HTTPException(status_code=404, detail="candidate not found")

    data = _read()
    projects = data.get("projects", [])
    project_id = req.id or _slugify(cand.get("name", "project"))

    # id 衝突回避
    base = project_id
    n = 2
    existing_ids = {p.get("id") for p in projects}
    while project_id in existing_ids:
        project_id = f"{base}-{n}"
        n += 1

    new_project = {
        "id": project_id,
        "name": cand.get("name", project_id),
        "category": req.category,
        "status": req.status,
        "priority": req.priority,
        "github_url": cand.get("github_url", ""),
        "live_url": "",
        "local_path": cand.get("local_path", ""),
        "memory_ref": "",
        "one_liner": req.one_liner or cand.get("last_email_subject", "") or cand.get("last_commit_message", ""),
        "next_action": req.next_action,
        "last_touched": cand.get("last_commit_date", "")[:10],
        "notes": f"Discovered from {cand.get('source')} on {cand.get('discovered_at','')[:10]}",
        "last_commit_sha": "",
        "last_commit_message": cand.get("last_commit_message", ""),
        "last_commit_date": cand.get("last_commit_date", ""),
        "last_commit_author": "",
        "uncommitted_changes": 0,
        "sync_source": "discovery",
        "sync_at": now_jst().isoformat(),
    }
    projects.append(new_project)
    data["projects"] = projects
    _write(data)

    # candidate から除去
    candidates = [c for c in candidates if c.get("id") != candidate_id]
    _write_candidates(candidates)

    return {"ok": True, "project": new_project}


@router.post("/projects/candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: str):
    candidates = _read_candidates()
    cand = next((c for c in candidates if c.get("id") == candidate_id), None)
    if not cand:
        raise HTTPException(status_code=404, detail="candidate not found")
    candidates = [c for c in candidates if c.get("id") != candidate_id]
    _write_candidates(candidates)
    rejected = _read_rejected()
    if candidate_id not in rejected:
        rejected.append(candidate_id)
        _write_rejected(rejected)
    return {"ok": True, "rejected": candidate_id}


@router.delete("/projects/candidates/clear-rejected")
def clear_rejected():
    """却下リストをリセット (もう一度提案させたい時用)"""
    _write_rejected([])
    return {"ok": True}


class HermesHandoffReq(BaseModel):
    task: str  # 「TODO 4 つ片付ける」「Stripe webhook 直す」など、Hermes に依頼したい具体タスク
    include_docs: bool = True
    include_commits: bool = True
    docs_max_chars: int = 3000


@router.post("/projects/{project_id}/hermes-handoff")
def hermes_handoff(project_id: str, req: HermesHandoffReq):
    """プロジェクトのコンテキスト (memory + 最近のコミット + ユーザータスク) を
    Hermes Desktop に貼り付けやすい形に整形して返す。frontend がクリップボードコピー。
    """
    data = _read()
    p = next((x for x in data.get("projects", []) if x.get("id") == project_id), None)
    if not p:
        raise HTTPException(status_code=404, detail=f"project {project_id} not found")

    parts: list[str] = []
    parts.append(f"# Koach OS → Hermes ハンドオフ: {p.get('name')}")
    parts.append("")
    parts.append("## あなたへの依頼")
    parts.append(req.task.strip() or "(タスク未指定)")
    parts.append("")

    parts.append("## プロジェクト概要")
    parts.append(f"- **ID**: `{p.get('id')}` / **カテゴリ**: {p.get('category')} / **優先度**: P{p.get('priority',3)}")
    parts.append(f"- **概要**: {p.get('one_liner') or '(未設定)'}")
    if p.get("github_url"):
        parts.append(f"- **GitHub**: {p.get('github_url')}")
    if p.get("live_url"):
        parts.append(f"- **Live**: {p.get('live_url')}")
    if p.get("local_path"):
        parts.append(f"- **ローカル**: `{p.get('local_path')}`")
    if p.get("next_action"):
        parts.append(f"- **現在の next_action**: {p.get('next_action')}")
    if p.get("last_touched"):
        unc = p.get("uncommitted_changes", 0)
        parts.append(f"- **最終接触**: {p.get('last_touched')}" + (f" ({unc} 件未コミット)" if unc else ""))
    parts.append("")

    if req.include_commits:
        recent = p.get("recent_commits") or []
        if recent:
            parts.append("## 最近のコミット (新しい順)")
            for c in recent[:10]:
                parts.append(f"- `{c.get('date','?')[:10]} {c.get('sha','')[:7]}` {c.get('message','')}")
            parts.append("")
        elif p.get("last_commit_message"):
            parts.append("## 最新コミット")
            parts.append(f"- `{p.get('last_commit_sha','')[:7]} {p.get('last_commit_date','')[:10]}` {p.get('last_commit_message')}")
            parts.append("")

    if req.include_docs:
        docs = p.get("docs") or []
        if docs:
            parts.append("## 資料 (memory / README / CLAUDE.md)")
            for d in docs:
                name = d.get("name", "?")
                content = (d.get("content", "") or "")[: req.docs_max_chars]
                parts.append(f"### {name}")
                parts.append(content)
                parts.append("")

    parts.append("---")
    parts.append("## あなたが満たすべき条件")
    parts.append("- ローカルでコード変更が必要なら `local_path` を起点に")
    parts.append("- 終了時、変更ファイル一覧と次の手 (テスト/デプロイ) を提示")
    parts.append("- 質問があれば 1 個だけ確認し、それ以外は仮定して進めてよい")
    parts.append("")
    parts.append(f"_Generated by Koach OS at {now_jst().isoformat()}_")

    prompt = "\n".join(parts)
    # Hermes に渡す deep link 候補 (まだ仕様未確定なので候補だけ)
    # 実機で動かないことを示すため、必要なら frontend 側で表示しない選択肢にする
    deep_link = None

    return {
        "project_id": project_id,
        "project_name": p.get("name"),
        "prompt": prompt,
        "char_count": len(prompt),
        "deep_link": deep_link,
        "generated_at": now_jst().isoformat(),
    }


class AdviseReq(BaseModel):
    focus: str = ""  # 「今日 2 時間ある」「リリース直前」「方向性で迷ってる」等の文脈ヒント
    engine: str = "claude"


def _trim_doc(content: str, max_chars: int = 4000) -> str:
    """資料を AI に渡す前に頭から max_chars に切る"""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n\n... (省略: 全 " + str(len(content)) + " 文字)"


@router.post("/projects/{project_id}/advise")
def advise_project(project_id: str, req: AdviseReq):
    """プロジェクト固有資料 (memory + README + git log) を AI に渡して
    「今やるべき具体アクション」を返す"""
    data = _read()
    p = next((x for x in data.get("projects", []) if x.get("id") == project_id), None)
    if not p:
        raise HTTPException(status_code=404, detail=f"project {project_id} not found")

    docs = p.get("docs") or []
    recent = p.get("recent_commits") or []
    docs_block = "\n\n".join(
        f"### {d.get('name', '?')} (source: {d.get('source','?')})\n{_trim_doc(d.get('content', ''))}"
        for d in docs
    ) or "(資料未同期。`python3 ~/.koach-os/scripts/sync_projects.py --with-docs` を叩くと拾われます)"

    commits_block = "\n".join(
        f"- {c.get('date','?')[:10]} {c.get('sha','')[:7]} {c.get('message','')}"
        for c in recent[:10]
    ) or "(コミット履歴未同期)"

    system_prompt = """あなたは志柿のプロジェクト専属アドバイザー (Alfred の AI 補佐)。
渡された 1 プロジェクトの資料 (memory ファイル / README / CLAUDE.md / 最近のコミット履歴) を読んで、
「今日やるべき具体的なアクション 3 つ」を返す。

## 出力形式 (Markdown)

### 📊 今の状況サマリ (1-2 文)
コミット履歴 + 資料から「今このプロジェクトはどこにいるか」を簡潔に。

### 🎯 今やるべき具体アクション (3 つ、優先順位順)
1. **アクション名** (見積もり時間)
   - なぜ今これか (1 文)
   - 着手の最初の一歩 (具体的に、コマンド or ファイル名 or 開く画面)
2. ...
3. ...

### ⚠ 詰まってる / 放置されてるもの (もしあれば、1-2 個)
- 資料から読み取れる「先送り」や「未解決」を指摘

### 💡 中長期で気になる視点 (1 つだけ、深追いしない)
- 今すぐじゃないけど忘れたら損するやつ

## ルール
- 一般論禁止。資料に書いてある固有名詞 (機能名 / ファイル名 / 数字) を使う
- 抽象名詞「〜性」NG、煽らない、励まさない、です/ます
- 「資料に基づくと」など前置きは省略、結論から
- アクションは「コーチが提案 → 自分が今からやれる」レベルに具体的に"""

    today = now_jst().strftime("%Y-%m-%d (%A)")
    user_msg = f"""今: {today}
プロジェクト: {p.get('name')} ({p.get('id')})
カテゴリ: {p.get('category')} / ステータス: {p.get('status')} / 優先度: P{p.get('priority',3)}
現在の next_action: {p.get('next_action') or '(未設定)'}
最終接触: {p.get('last_touched') or '未記録'} ({p.get('uncommitted_changes', 0)} 件未コミット)
URL: {p.get('github_url') or '-'} / {p.get('live_url') or '-'}

## ユーザーの今の文脈
{req.focus or '(指定なし)'}

## 最近のコミット (新しい順)
{commits_block}

## プロジェクト資料
{docs_block}

上記資料を踏まえ、このプロジェクトに対する「今日やるべき具体アクション 3 つ」を出してください。"""

    engine = req.engine if req.engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS[engine]

    try:
        out = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=system_prompt,
            engine=engine,
            model=model,
            max_tokens=2000,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"advise failed: {e}")

    return {
        "generated_at": now_jst().isoformat(),
        "project_id": project_id,
        "engine_used": engine,
        "model_used": model,
        "advice": out,
        "docs_count": len(docs),
        "commits_used": len(recent[:10]),
    }
