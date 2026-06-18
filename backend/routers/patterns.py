"""
GET /api/patterns       — 直近のあなたのパターン分析 (cached)
POST /api/patterns/regenerate — AI で再生成

分析対象 (過去 30 日):
- completions.jsonl   (何を / いつ片付けたか)
- focus_sessions      (集中ブロックの実績)
- decisions / failures
- private_chat        (繰り返し悩んでいるテーマ)
- memos               (最近の関心)
- calendar events     (どう時間を使ったか)
- backlog の残り     (溜まり続けているもの)

出力: 数字付きの具体的観察 5〜8 件。煽らない、一般論禁止、自分のデータから抽出。
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from data_manager import (
    DATA_DIR,
    DECISIONS_FILE,
    FAILURES_FILE,
    MEMOS_FILE,
    now_jst,
    read_jsonl,
    timestamp_jst,
)
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

PATTERNS_CACHE = DATA_DIR / "patterns_cache.json"
PRIVATE_CHAT_FILE = DATA_DIR / "private_chat.jsonl"
FOCUS_FILE = DATA_DIR / "focus_sessions.jsonl"
COMPLETIONS_FILE = DATA_DIR / "completions.jsonl"

CACHE_TTL_HOURS = 12  # 半日に1回まで


def _gather_signals(days: int = 30) -> dict:
    now = now_jst()
    cutoff_date = (now.date() - timedelta(days=days - 1)).isoformat()
    cutoff_iso = (now - timedelta(days=days)).isoformat()

    # completions
    try:
        from routers.completions import _current_state
        completions = [
            v for (_k, _r, d), v in _current_state().items() if d >= cutoff_date
        ]
        completions.sort(key=lambda x: x.get("date", ""))
    except Exception:
        completions = []

    # focus
    focus_sessions = []
    if FOCUS_FILE.exists():
        for line in FOCUS_FILE.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if e.get("date", "") >= cutoff_date and e.get("completed"):
                    focus_sessions.append(e)
            except Exception:
                continue

    # decisions / failures
    decisions = [d for d in read_jsonl(DECISIONS_FILE) if d.get("timestamp", "") >= cutoff_iso]
    failures = [f for f in read_jsonl(FAILURES_FILE) if f.get("timestamp", "") >= cutoff_iso]

    # private chat (user 発話のみ)
    priv_lines = []
    if PRIVATE_CHAT_FILE.exists():
        for line in PRIVATE_CHAT_FILE.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if e.get("role") == "user" and e.get("timestamp", "") >= cutoff_iso:
                    priv_lines.append(e.get("content", "")[:300])
            except Exception:
                continue

    # memos (最新 40)
    memo_state = {}
    for m in read_jsonl(MEMOS_FILE):
        if not m.get("id"):
            continue
        if m.get("_deleted"):
            memo_state.pop(m["id"], None)
            continue
        memo_state[m["id"]] = m
    memos = sorted(memo_state.values(), key=lambda x: x.get("created_at", ""), reverse=True)[:40]

    # calendar last days
    cal_events = []
    try:
        from gcal import is_configured, list_events_range
        if is_configured():
            start_str = (now - timedelta(days=days - 1)).strftime("%Y-%m-%d")
            end_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
            cal_events = list_events_range(start_str, end_str)
    except Exception:
        pass

    # backlog (current open)
    backlog_open = []
    try:
        from routers.productivity import _load_backlog
        backlog_open = [b for b in _load_backlog() if not b.get("done")]
    except Exception:
        pass

    # work_log (実績台帳): 実際にやり遂げた作業 + 使った AI
    work_log = []
    try:
        from routers.work_log import _materialize as _wl_materialize
        work_log = [w for w in _wl_materialize().values() if w.get("date", "") >= cutoff_date]
        work_log.sort(key=lambda x: x.get("date", ""))
    except Exception:
        work_log = []

    return {
        "completions": completions,
        "focus_sessions": focus_sessions,
        "decisions": decisions,
        "failures": failures,
        "private_lines": priv_lines,
        "memos": memos,
        "cal_events": cal_events,
        "backlog_open": backlog_open,
        "work_log": work_log,
        "days": days,
    }


def _signals_to_text(s: dict) -> str:
    days = s["days"]
    parts = [f"## 過去 {days} 日のデータ"]

    parts.append(f"\n### 完了ログ ({len(s['completions'])}件) — 直近20")
    for c in s["completions"][-20:]:
        parts.append(f"- {c.get('date','')[5:]} [{c.get('category','')}] {c.get('title','')}")

    work_log = s.get("work_log", [])
    parts.append(f"\n### 実績台帳 work_log ({len(work_log)}件) — 直近20")
    for w in work_log[-20:]:
        eng = f" [AI:{w.get('engine')}]" if w.get("engine") else ""
        mins = f" {w.get('minutes')}分" if w.get("minutes") else ""
        parts.append(f"- {w.get('date','')[5:]} [{w.get('category','')}] {w.get('title','')}{eng}{mins}")
    eng_cat: dict[str, dict[str, int]] = {}
    for w in work_log:
        e = w.get("engine")
        if not e:
            continue
        cat = w.get("category") or "(未分類)"
        d = eng_cat.setdefault(cat, {})
        d[e] = d.get(e, 0) + 1
    if eng_cat:
        parts.append("- 作業カテゴリ別の AI 使用: " + "; ".join(
            f"{cat}=" + ",".join(f"{e}:{n}" for e, n in sorted(ec.items(), key=lambda x: -x[1]))
            for cat, ec in eng_cat.items()
        ))

    parts.append(f"\n### 集中セッション ({len(s['focus_sessions'])}件)")
    by_cat = {}
    for fs in s["focus_sessions"]:
        cat = fs.get("category", "other")
        by_cat[cat] = by_cat.get(cat, 0) + int(fs.get("actual_minutes", 0))
    for k, v in sorted(by_cat.items(), key=lambda x: -x[1]):
        parts.append(f"- {k}: {v} 分")

    parts.append(f"\n### Calendar 実績 ({len(s['cal_events'])}件) — 抜粋")
    by_hour = {}  # 開始時刻 (時)
    by_weekday = {}
    for ev in s["cal_events"]:
        iso = ev.get("start_iso", "")
        if len(iso) > 13 and "T" in iso:
            try:
                h = int(iso[11:13])
                by_hour[h] = by_hour.get(h, 0) + 1
                from datetime import datetime as _dt
                d = _dt.fromisoformat(iso.replace("Z", "+00:00"))
                wd = ["月","火","水","木","金","土","日"][d.weekday()]
                by_weekday[wd] = by_weekday.get(wd, 0) + 1
            except Exception:
                pass
    if by_hour:
        parts.append("- 開始時刻分布: " + ", ".join(f"{h}時:{n}" for h, n in sorted(by_hour.items())))
    if by_weekday:
        parts.append("- 曜日分布: " + ", ".join(f"{k}:{n}" for k, n in by_weekday.items()))

    parts.append(f"\n### 決定 ({len(s['decisions'])}件) — 直近10")
    for d in s["decisions"][-10:]:
        parts.append(f"- {d.get('title','')}: {d.get('reasoning','')[:100]}")

    parts.append(f"\n### 失敗ログ ({len(s['failures'])}件)")
    for f in s["failures"][-10:]:
        parts.append(f"- {f.get('what','')} → {f.get('lesson','')[:100]}")

    parts.append(f"\n### Private chat の user 発話 ({len(s['private_lines'])}件) — 直近20")
    for p in s["private_lines"][-20:]:
        parts.append(f"- {p[:200]}")

    parts.append(f"\n### Memos ({len(s['memos'])}件) — 最新10")
    for m in s["memos"][:10]:
        c = (m.get("content", "") or "").replace("\n", " ")[:150]
        parts.append(f"- {c}")

    parts.append(f"\n### 未完バックログ ({len(s['backlog_open'])}件)")
    for b in s["backlog_open"][:15]:
        parts.append(f"- [{b.get('urgency','m')}] [{b.get('category','')}] {b.get('title','')}")

    return "\n".join(parts)


SYSTEM_PROMPT = """あなたは志柿のデータ分析担当。過去 30 日の本人ログから「観察できるパターン」を抽出する。

出力ルール:
- 数字付きの具体的観察を 5〜8 件、Markdown 箇条書きで
- 各観察は「事実 → 含意」の 2 行: 1 行目は数字を伴う事実、2 行目は「だからこうかもしれない」「これは…の兆候」など
- バイアス・偏り・盲点を率直に指摘 (家族時間が削られている、特定カテゴリだけ未完率高い等)
- work_log がある場合、使った AI の偏り (慣れで同じ AI に投げて手戻りが多い作業がないか等) も観察対象に含める
- 強み・うまく行っているパターンも 1〜2 件
- 一般論・精神論 NG ("頑張ってる" のような感想 NG)
- 抽象名詞「〜性」「重要性」「必要性」NG
- em ダッシュ禁止
- 煽らない、諦めさせない (止めろではなく、別の入れ方を提示)
- 一人称「自分」、です/ます調

最後に以下のサブセクションをそれぞれ 1〜2 文で追加:

## 強み (続けるべき)
- ...

## 注意点 (補正が要る)
- ...

## 来週の小さな実験 (1 つだけ)
- ...

全体 600〜900 字。"""


def _generate(engine: str = "claude") -> dict:
    signals = _gather_signals(days=30)
    sig_text = _signals_to_text(signals)

    if engine not in DEFAULT_MODELS:
        engine = "claude"
    model = DEFAULT_MODELS[engine]

    try:
        out = call_ai(
            messages=[{"role": "user", "content": sig_text}],
            system=SYSTEM_PROMPT,
            engine=engine,
            model=model,
            max_tokens=1800,
        )
    except Exception as e:
        raise HTTPException(500, f"pattern generation failed: {e}")

    now = now_jst()
    cache = {
        "generated_at": now.isoformat(),
        "engine_used": engine,
        "model_used": model,
        "data_summary": {
            "completions": len(signals["completions"]),
            "focus_sessions": len(signals["focus_sessions"]),
            "decisions": len(signals["decisions"]),
            "failures": len(signals["failures"]),
            "private_lines": len(signals["private_lines"]),
            "memos": len(signals["memos"]),
            "cal_events": len(signals["cal_events"]),
            "backlog_open": len(signals["backlog_open"]),
            "work_log": len(signals["work_log"]),
        },
        "report": out,
    }
    PATTERNS_CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
    return cache


def _read_cache() -> dict | None:
    if not PATTERNS_CACHE.exists():
        return None
    try:
        return json.loads(PATTERNS_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None


def _cache_fresh(cache: dict) -> bool:
    try:
        from datetime import datetime as _dt
        ts = _dt.fromisoformat(cache.get("generated_at", ""))
        return (now_jst() - ts) < timedelta(hours=CACHE_TTL_HOURS)
    except Exception:
        return False


@router.get("/patterns")
def get_patterns(engine: str = Query("claude"), force: bool = Query(False)):
    cache = _read_cache()
    if cache and not force and _cache_fresh(cache):
        cache["cached"] = True
        return cache
    cache = _generate(engine=engine)
    cache["cached"] = False
    return cache


@router.post("/patterns/regenerate")
def regenerate_patterns(engine: str = Query("claude")):
    cache = _generate(engine=engine)
    cache["cached"] = False
    return cache
