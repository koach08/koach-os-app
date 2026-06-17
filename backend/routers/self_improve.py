"""
自己改善ループ — 過去ログを分析して、ユーザーに合わせた次の打ち手を提案。

GET  /api/self-improve/report?days=7&engine=claude
- interaction_logs.jsonl の過去 N 日を読む
- メタ AI が分析 (使用パターン / エンジン分布 / 改善提案 / 注意点)
- read-only。prompt や挙動の自動書換はしない。

POST /api/self-improve/snapshot
- 直近レポートを data/self_improve_snapshots.jsonl に保存
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data_manager import DATA_DIR, LOGS_FILE, read_jsonl, now_jst, timestamp_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

SNAPSHOTS_FILE = DATA_DIR / "self_improve_snapshots.jsonl"


META_SYSTEM = """あなたは志柿浩一郎の使用パターン分析担当 (メタ AI)。
ログから本人の傾向を見て、 koach-os をどう進化させると良いかを冷静に提案する。

ルール:
- 過去 N 日のログ抜粋を読む
- 「迎合しないアプリ」というビジョンを尊重。 媚びない、 必要なら厳しい指摘
- 抽象名詞「〜性」「重要性」、 過度な絵文字、 です/ます調連打は避ける
- 体言止め可
- 出力は構造化、 各セクション 3-5 項目以内

出力フォーマット (Markdown):

## 使用パターン (上位 5)
- ...

## エンジン分布
- claude: N 回 (XX %)
- gpt: ...

## 傾向 / 強み
- ...

## 弱点 / 触れていない領域
- ...

## 次の打ち手 (提案 3 件)
1. ...
2. ...
3. ...
"""


class ReportReq(BaseModel):
    days: int = 7
    engine: str = "claude"


def _load_logs_window(days: int) -> list[dict]:
    cutoff = (now_jst() - timedelta(days=days)).isoformat()
    return read_jsonl(LOGS_FILE, filter_fn=lambda x: x.get("timestamp", "") >= cutoff)


def _stats(logs: list[dict]) -> dict:
    engines = Counter()
    domains = Counter()
    task_types = Counter()
    for lg in logs:
        eng = (lg.get("routing") or {}).get("engine") or "unknown"
        engines[eng] += 1
        domains[lg.get("domain") or "unknown"] += 1
        task_types[lg.get("task_type") or "unknown"] += 1
    return {
        "engines": engines.most_common(),
        "domains": domains.most_common(),
        "task_types": task_types.most_common(10),
        "total": len(logs),
    }


@router.get("/self-improve/report")
def report(
    days: int = Query(7, ge=1, le=90),
    engine: str = Query("claude"),
):
    logs = _load_logs_window(days)
    if not logs:
        return {
            "ok": True,
            "stats": {"total": 0},
            "report": "(過去 N 日にログなし。 chat を使うとここに集まる)",
            "days": days,
        }
    stats = _stats(logs)

    # ログは多すぎるので user_input_preview のみ最大 80 件抜粋
    samples = [
        {
            "ts": lg.get("timestamp", "")[:16],
            "engine": (lg.get("routing") or {}).get("engine"),
            "domain": lg.get("domain"),
            "task": lg.get("task_type"),
            "input": (lg.get("user_input_preview") or lg.get("user_input") or "")[:120],
        }
        for lg in logs[-80:]
    ]
    user_msg = (
        f"過去 {days} 日の chat ログ ({stats['total']} 件) を分析してください。\n\n"
        f"=== 統計 ===\n{json.dumps(stats, ensure_ascii=False, indent=2)}\n\n"
        f"=== サンプル (最新 80 件) ===\n{json.dumps(samples, ensure_ascii=False, indent=2)}"
    )
    eng = engine if engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS[eng]
    try:
        out = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=META_SYSTEM,
            engine=eng,
            model=model,
            max_tokens=2000,
        )
    except Exception as e:
        raise HTTPException(500, f"meta AI failed: {e}")

    return {
        "ok": True,
        "days": days,
        "stats": stats,
        "report": out,
        "engine": eng,
        "model": model,
    }


@router.post("/self-improve/snapshot")
def snapshot(req: ReportReq):
    """直近レポートを保存 (週次 baseline を残す用途)"""
    r = report(days=req.days, engine=req.engine)
    entry = {
        "timestamp": timestamp_jst(),
        "days": req.days,
        "stats": r["stats"],
        "report": r["report"],
        "engine": r.get("engine"),
        "model": r.get("model"),
    }
    with SNAPSHOTS_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"ok": True, "saved": True}


@router.get("/self-improve/snapshots")
def list_snapshots(limit: int = Query(20)):
    if not SNAPSHOTS_FILE.exists():
        return {"items": [], "count": 0}
    items: list[dict] = []
    for line in SNAPSHOTS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            items.append(json.loads(line))
        except Exception:
            continue
    items.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return {"items": items[:limit], "count": len(items)}
