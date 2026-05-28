"""
日程調整 + Deep Work 提案。

GET  /api/scheduling/free-slots?days_ahead=2&min_minutes=45 — Calendar の隙間検出
POST /api/scheduling/deep-work-plan — 隙間 × バックログ × pending email を Claude が割り当て
POST /api/scheduling/draft-reply    — 受信メールに対する候補時間付き返信案
"""

from __future__ import annotations

import json
from datetime import datetime, time, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data_manager import now_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()


JST = timezone(timedelta(hours=9))


def _to_local(iso: str) -> datetime | None:
    if not iso:
        return None
    try:
        if "T" not in iso:  # all-day
            return None
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return d.astimezone(JST)
    except Exception:
        return None


def _find_free_slots(
    days_ahead: int = 2,
    min_minutes: int = 45,
    work_start_hour: int = 8,
    work_end_hour: int = 22,
) -> list[dict]:
    """Calendar の予定を見て、work_start 〜 work_end の間の空きを探す。"""
    try:
        from gcal import is_configured, list_events_range
    except Exception:
        return []
    if not is_configured():
        return []

    now = now_jst()
    start_date = now.strftime("%Y-%m-%d")
    end_date = (now + timedelta(days=days_ahead + 1)).strftime("%Y-%m-%d")
    try:
        events = list_events_range(start_date=start_date, end_date=end_date)
    except Exception:
        return []

    # 各日 work_start - work_end のレンジを構築
    days = []
    for d_off in range(days_ahead + 1):
        d = (now.date() + timedelta(days=d_off))
        ds = datetime.combine(d, time(work_start_hour, 0)).replace(tzinfo=JST)
        de = datetime.combine(d, time(work_end_hour, 0)).replace(tzinfo=JST)
        # 今日の場合は now 以降
        if d_off == 0:
            ds = max(ds, now)
            if ds >= de:
                continue
        days.append({"date": d, "start": ds, "end": de})

    # 日ごとに busy intervals を集める
    by_day: dict[str, list[tuple[datetime, datetime]]] = {}
    for ev in events:
        s = _to_local(ev.get("start_iso", ""))
        e = _to_local(ev.get("end_iso", ""))
        if not s or not e:
            continue
        key = s.date().isoformat()
        by_day.setdefault(key, []).append((s, e))

    slots: list[dict] = []
    for day in days:
        key = day["date"].isoformat()
        busy = sorted(by_day.get(key, []))
        cursor = day["start"]
        for bs, be in busy:
            if be <= cursor or bs >= day["end"]:
                continue
            if bs > cursor:
                gap_min = int((bs - cursor).total_seconds() / 60)
                if gap_min >= min_minutes:
                    slots.append({
                        "date": key,
                        "start_iso": cursor.isoformat(),
                        "end_iso": bs.isoformat(),
                        "minutes": gap_min,
                    })
            cursor = max(cursor, be)
        if cursor < day["end"]:
            gap_min = int((day["end"] - cursor).total_seconds() / 60)
            if gap_min >= min_minutes:
                slots.append({
                    "date": key,
                    "start_iso": cursor.isoformat(),
                    "end_iso": day["end"].isoformat(),
                    "minutes": gap_min,
                })

    return slots


@router.get("/scheduling/free-slots")
def free_slots(
    days_ahead: int = Query(2, ge=0, le=14),
    min_minutes: int = Query(45, ge=15, le=480),
    work_start_hour: int = Query(8),
    work_end_hour: int = Query(22),
):
    slots = _find_free_slots(
        days_ahead=days_ahead,
        min_minutes=min_minutes,
        work_start_hour=work_start_hour,
        work_end_hour=work_end_hour,
    )
    total = sum(s["minutes"] for s in slots)
    return {"slots": slots, "count": len(slots), "total_minutes": total}


class DeepWorkReq(BaseModel):
    days_ahead: int = 2
    min_minutes: int = 45
    engine: str = "claude"


SYSTEM_PROMPT = """あなたは志柿の deep work アサインメント担当。

入力: (a) Calendar の空き slot 一覧, (b) Coach バックログ (やりたい仕事), (c) 対応待ちメール一覧

出力ルール:
- 各 slot に「何を / どの AI ツールで / なぜそれを今」を割り当てる
- AI ツール推奨基準:
  - Claude Code: コード書き直し・PR ドラフト・既存コードベース改修 (ローカル CLI 必要)
  - Codex: 単発スクリプト・新規プロジェクトひな型
  - Claude.ai: 長文の構成・論文・戦略文書
  - ChatGPT Canvas: マルチモーダル試作
  - Gemini AI Studio: PDF / 動画 / 長尺音声分析
  - Firefly: 販売デザイン (商用クリーン)
  - Koach OS Agent: メール仕分け・自分データ検索 + 行動
  - 道具不要: 紙メモ・ホワイトボード思考・読書
- 1 slot に 1 タスク (集中する)
- 60 分未満の slot は「メール返信まとめ」や「短時間タスク」を充てる
- 家族時間・休息時間と被るブロックには deep work 入れない
- 「家族時間」「散歩」「休息」を 1 つは含める (詰め込みすぎない)

フォーマット (Markdown):

## 提案スケジュール (today + tomorrow + N)

### YYYY-MM-DD (曜日)
- HH:MM-HH:MM (N 分) — タスク名 [カテゴリ絵文字]
  - 道具: ツール名 (理由)
  - 今やる理由: ...

## カバーできないタスク
- (slot が足りないバックログ項目)
- (今週の繰り越し提案)

## 注意
- 1 行で「無理してる箇所」「家族・健康とのバランス」指摘

トーン: 簡潔、です/ます調、抽象名詞「〜性」NG、煽らない、諦めさせない、一人称「自分」。600〜1000 字。"""


@router.post("/scheduling/deep-work-plan")
def deep_work_plan(req: DeepWorkReq):
    slots = _find_free_slots(days_ahead=req.days_ahead, min_minutes=req.min_minutes)

    # backlog
    try:
        from routers.productivity import _load_backlog
        today_iso = now_jst().strftime("%Y-%m-%d")
        backlog = [
            b for b in _load_backlog()
            if not b.get("done")
            and (not b.get("defer_until") or b["defer_until"] <= today_iso)
        ]
    except Exception:
        backlog = []

    # pending email
    try:
        from routers.email_watch import _load as load_email
        ew = load_email()
        today_str = now_jst().strftime("%Y-%m-%d")
        pending_email = [
            it for it in (ew.get("items", {}) or {}).values()
            if not it.get("done_at")
            and (not it.get("snooze_until") or it["snooze_until"] <= today_str)
        ]
    except Exception:
        pending_email = []

    slot_text = "\n".join(
        f"- {s['date']} {s['start_iso'][11:16]}〜{s['end_iso'][11:16]} ({s['minutes']} 分)"
        for s in slots
    ) or "(空き slot なし)"

    backlog_text = "\n".join(
        f"- [{b.get('urgency','m')}][{b.get('category','other')}] {b.get('title','')} (推定{b.get('estimated_minutes',60)}分)"
        + (f" 期限 {b['due_date']}" if b.get("due_date") else "")
        for b in backlog[:25]
    ) or "(バックログなし)"

    email_text = "\n".join(
        f"- [{it.get('urgency','m')}] {it.get('subject','')[:60]} from {it.get('from','')[:40]} ({it.get('action_hint','')})"
        for it in pending_email[:15]
    ) or "(対応待ちメールなし)"

    user_msg = f"""今: {now_jst().strftime('%Y-%m-%d %H:%M (%A)')}

## Calendar 空き slot (今日〜{req.days_ahead}日先)
{slot_text}

## Coach バックログ (未完)
{backlog_text}

## 対応待ちメール
{email_text}

各 slot に何をいつ何で進めるか提案してください。"""

    engine = req.engine if req.engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS[engine]
    try:
        plan = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=SYSTEM_PROMPT,
            engine=engine,
            model=model,
            max_tokens=2500,
        )
    except Exception as e:
        raise HTTPException(500, f"plan failed: {e}")

    return {
        "generated_at": now_jst().isoformat(),
        "slot_count": len(slots),
        "free_total_minutes": sum(s["minutes"] for s in slots),
        "backlog_count": len(backlog),
        "pending_email_count": len(pending_email),
        "engine_used": engine,
        "model_used": model,
        "plan": plan,
        "slots": slots,
    }


class DraftReplyReq(BaseModel):
    original_subject: str
    original_body: str = ""
    sender: str = ""
    duration_min: int = 60
    days_ahead: int = 14
    earliest_days_from_now: int = 1  # 「翌日以降」など
    constraints: str = ""  # 「午前のみ」「火木 NG」など
    engine: str = "claude"


@router.post("/scheduling/draft-reply")
def draft_reply(req: DraftReplyReq):
    """元メール + 制約 → 候補 3 時刻 + 日本語返信下書き。"""
    # earliest_days_from_now 後の空き slot を取得
    slots = _find_free_slots(days_ahead=req.days_ahead, min_minutes=req.duration_min)
    # earliest_days_from_now 以降にフィルタ
    cutoff = (now_jst().date() + timedelta(days=req.earliest_days_from_now)).isoformat()
    eligible = [s for s in slots if s["date"] >= cutoff][:8]

    if not eligible:
        return {"candidates": [], "reply": "(候補 slot なし。constraints を緩めるか days_ahead を伸ばしてください)"}

    cand_text = "\n".join(
        f"- {s['date']} {s['start_iso'][11:16]}〜{(_to_local(s['end_iso']) or _to_local(s['start_iso'])).strftime('%H:%M')} ({s['minutes']} 分)"
        for s in eligible
    )

    system = """日本語の丁寧ビジネスメール返信を書く。
- 件名は元の Re: そのまま
- 候補は 3 つ提示、優先順をつけずに並べる
- ですます調、過剰な敬語にしない (志柿浩一郎スタイル)
- 抽象名詞「〜性」NG
- 「ご都合いかがでしょうか」で締める
- 候補時刻は 1 行に 1 つ、箇条書きで

出力フォーマット (そのまま貼り付けて使う):

(本文のみ。署名は本人が後で付ける)"""

    user = f"""## 元メール
From: {req.sender}
Subject: {req.original_subject}
Body: {req.original_body[:1500]}

## 候補 slot ({len(eligible)} 件、ここから 3 つ選んで)
{cand_text}

## 所要時間
{req.duration_min} 分

## 追加制約
{req.constraints or "(なし)"}

候補 3 つを含む返信本文を書いてください。"""

    engine = req.engine if req.engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS[engine]
    try:
        reply = call_ai(
            messages=[{"role": "user", "content": user}],
            system=system,
            engine=engine,
            model=model,
            max_tokens=1200,
        )
    except Exception as e:
        raise HTTPException(500, f"draft failed: {e}")

    return {
        "candidates": eligible,
        "reply": reply,
        "generated_at": now_jst().isoformat(),
        "engine_used": engine,
    }
