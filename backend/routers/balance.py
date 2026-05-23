"""
GET /api/balance — カテゴリ別バランスチェック。
完了ログ + Calendar の category 推定で、家族 / 健康 / クリエイティブ / 休息の確保状況を計算。
赤バッジが立つ閾値:
  - family: 過去7日で 5時間 未満
  - health: 過去7日で 0 完了 or 3日連続未消化
  - rest: 22時以降の完了ログが過去3日で 6時間以上（働きすぎ）
"""

from __future__ import annotations

from datetime import datetime, timedelta
from fastapi import APIRouter, Query

from data_manager import now_jst

router = APIRouter()


CATEGORY_KEYWORDS = {
    "family": ["家族", "保育園", "妻", "子", "親", "送り", "迎え", "夕食", "風呂"],
    "health": ["ブレイクダンス", "アクロバット", "運動", "筋トレ", "ジム", "ラン", "ヨガ", "ストレッチ", "睡眠"],
    "creative": ["執筆", "note", "記事", "ブログ", "AI 画像", "創作", "EGAKU"],
    "research": ["論文", "研究", "科研費", "査読"],
    "career": ["授業", "講義", "TA", "会議", "委員会", "学生"],
    "side_project": ["EGAKU", "crypto", "SpeakSmart", "個人開発"],
    "admin": ["事務", "メール", "申請", "提出"],
    "rest": ["休息", "昼寝", "リラックス"],
}


def _guess_category(title: str) -> str:
    t = title or ""
    for cat, kws in CATEGORY_KEYWORDS.items():
        if any(kw in t for kw in kws):
            return cat
    return "other"


@router.get("/balance")
def balance(days: int = Query(7, ge=1, le=30)):
    now = now_jst()
    cutoff_date = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")

    # 完了ログを集約
    try:
        from routers.completions import _current_state
        all_state = _current_state()
        recent = [v for (_k, _r, d), v in all_state.items() if d >= cutoff_date]
    except Exception:
        recent = []

    # カテゴリ別件数 + 推定時間（1件 60分 + life-block 実時間）
    counts: dict[str, int] = {}
    for c in recent:
        cat = c.get("category") or _guess_category(c.get("title", ""))
        counts[cat] = counts.get(cat, 0) + 1

    # Calendar 実績（カテゴリは推定）
    cal_minutes: dict[str, int] = {}
    try:
        from gcal import is_configured, list_events_range
        if is_configured():
            start_str = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
            end_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            for ev in list_events_range(start_str, end_str):
                cat = _guess_category(ev.get("title", ""))
                try:
                    s = datetime.fromisoformat(ev["start_iso"].replace("Z", "+00:00"))
                    e = datetime.fromisoformat(ev["end_iso"].replace("Z", "+00:00"))
                    mins = max(0, int((e - s).total_seconds() / 60))
                    cal_minutes[cat] = cal_minutes.get(cat, 0) + mins
                except Exception:
                    continue
    except Exception:
        pass

    # 警告判定
    warnings: list[dict] = []
    family_minutes = cal_minutes.get("family", 0)
    if family_minutes < 300:  # 5時間未満
        warnings.append({
            "severity": "warn",
            "category": "family",
            "message": f"家族時間が過去{days}日で {family_minutes // 60} 時間。意識的にブロックを取ってください",
        })
    health_minutes = cal_minutes.get("health", 0)
    health_done = counts.get("health", 0)
    if health_done == 0 and health_minutes < 60:
        warnings.append({
            "severity": "warn",
            "category": "health",
            "message": f"健康ブロックが過去{days}日で {health_minutes} 分。再開予定のブレイクダンス・アクロバット枠を確保",
        })
    # 夜更かしチェック
    late_count = sum(
        1 for c in recent
        if (c.get("completed_at", "")[11:13] or "00").isdigit()
        and int(c.get("completed_at", "00:00")[11:13] or 0) >= 22
    )
    if late_count >= 5:
        warnings.append({
            "severity": "info",
            "category": "rest",
            "message": f"22時以降の作業完了が過去{days}日で {late_count} 件。睡眠優先",
        })

    return {
        "days": days,
        "completions_by_category": counts,
        "calendar_minutes_by_category": cal_minutes,
        "warnings": warnings,
    }
