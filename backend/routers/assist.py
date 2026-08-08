"""
Assist — 横断アシスト系エンドポイント (既存データを集約して判断を助ける)。

- GET  /api/next-action : 今この瞬間にやるべき一手を理由つきで1つ提示 (忖度しない)
- GET  /api/triage      : 対応待ちメール + backlog + 期限切れタスクを1つに集約 (任意で AI 優先順位)
- GET  /api/ai-usage    : worklog の engine タグ + routine 実行から AI 利用状況を集計
- GET  /api/assist/order: 未対応を全部見て「早く片付けるべき順」を構造化ランキング (利益加点つき)
- POST /api/assist/plan : 選んだ1件を「最短手順 + 詰まった時の一歩 + 文面案 + 利益への効き」に分解

既存ローダを読むだけ。書き込み・既存ファイルへの干渉なし。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from data_manager import now_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()


def _parse_json(raw: str):
    """AI 出力から JSON を頑健に取り出す。```json フェンスや前後の地の文を許容。"""
    if not raw:
        return None
    s = raw.strip()
    m = re.search(r"```(?:json)?\s*(.+?)\s*```", s, re.DOTALL)
    if m:
        s = m.group(1).strip()
    # 最初の { か [ から最後の } か ] までを拾う
    starts = [i for i in (s.find("{"), s.find("[")) if i >= 0]
    ends = [i for i in (s.rfind("}"), s.rfind("]")) if i >= 0]
    if starts and ends:
        s = s[min(starts): max(ends) + 1]
    try:
        return json.loads(s)
    except Exception:
        return None


# ─── 共通: 文脈収集 ───
def _today() -> str:
    return now_jst().strftime("%Y-%m-%d")


def _pending_emails(limit: int = 8) -> list[dict]:
    try:
        from routers.email_watch import _load, _is_pending, _days_since
        today = _today()
        out = []
        for it in (_load().get("items", {}) or {}).values():
            if not _is_pending(it, today):
                continue
            out.append({
                "subject": it.get("subject", "")[:80],
                "from": it.get("from", "")[:60],
                "urgency": it.get("urgency", "medium"),
                "deadline_date": it.get("deadline_date"),
                "days_since": _days_since(it.get("received_at", "")),
            })
        rank = {"high": 0, "medium": 1, "low": 2}
        out.sort(key=lambda x: (rank.get(x["urgency"], 1), -x["days_since"]))
        return out[:limit]
    except Exception:
        return []


def _open_backlog(limit: int = 12) -> list[dict]:
    try:
        from routers.productivity import _load_backlog
        rank = {"high": 0, "medium": 1, "low": 2}
        out = [
            {"title": b.get("title", ""), "category": b.get("category", ""),
             "urgency": b.get("urgency", "medium"), "due_date": b.get("due_date")}
            for b in _load_backlog() if not b.get("done")
        ]
        out.sort(key=lambda x: (rank.get(x["urgency"], 1), x.get("due_date") or "9999"))
        return out[:limit]
    except Exception:
        return []


def _overdue_tasks(limit: int = 12) -> list[dict]:
    try:
        from routers.tasks import _materialize_state
        today = _today()
        out = []
        for t in _materialize_state().values():
            if t.get("status") == "done":
                continue
            due = t.get("due_date")
            out.append({
                "title": t.get("title", ""),
                "due_date": due,
                "status": t.get("status", "todo"),
                "overdue": bool(due and due < today),
            })
        out.sort(key=lambda x: (not x["overdue"], x.get("due_date") or "9999"))
        return out[:limit]
    except Exception:
        return []


def _todays_calendar(remaining_only: bool = True) -> list[dict]:
    try:
        from gcal import is_configured, get_events
        if not is_configured():
            return []
        now_iso = now_jst().isoformat()
        out = []
        for e in get_events(days_ahead=0) or []:
            start = e.get("start", "") or ""
            if remaining_only and start and "T" in start and start < now_iso:
                continue
            out.append({"title": e.get("summary", ""), "start": start, "location": e.get("location", "")})
        return out
    except Exception:
        return []


def _recent_worklog(limit: int = 5) -> list[dict]:
    try:
        from routers.work_log import _materialize as _wl
        recent = sorted(_wl().values(), key=lambda w: w.get("date", ""), reverse=True)[:limit]
        return [{"date": w.get("date", ""), "title": w.get("title", ""), "category": w.get("category", "")} for w in recent]
    except Exception:
        return []


# ─── /next-action ───
@router.get("/next-action")
def next_action(engine: str = Query("claude")):
    now = now_jst()
    cal = _todays_calendar(remaining_only=True)
    emails = _pending_emails(6)
    backlog = _open_backlog(8)
    tasks = _overdue_tasks(8)
    worklog = _recent_worklog(5)

    ctx = {
        "now": now.strftime("%Y-%m-%d %H:%M (%A)"),
        "remaining_calendar": cal,
        "pending_emails": emails,
        "open_backlog": backlog,
        "tasks": tasks,
        "recent_done": worklog,
    }

    prompt = (
        f"今は {ctx['now']}。以下のデータを見て、『今この瞬間にやるべき一手』を1つだけ選んでください。\n\n"
        f"=== 今日の残り予定 ===\n{json.dumps(cal, ensure_ascii=False)}\n\n"
        f"=== 対応待ちメール ===\n{json.dumps(emails, ensure_ascii=False)}\n\n"
        f"=== 未完バックログ ===\n{json.dumps(backlog, ensure_ascii=False)}\n\n"
        f"=== 期限つきタスク ===\n{json.dumps(tasks, ensure_ascii=False)}\n\n"
        f"=== 直近やり終えた事 ===\n{json.dumps(worklog, ensure_ascii=False)}\n"
    )
    system = (
        "あなたは志柿の相棒 AI。今やるべき一手を1つだけ即断で薦める。\n"
        "ルール:\n"
        "- 出力は『■ 今やる一手』(1行) → 『■ 理由』(2-3行) → 『■ 次の候補』(1-2個) の順\n"
        "- 締切の近さ・放置日数・次の予定までの空き時間を根拠に。数字を引く\n"
        "- 迎合しない。先送りしている物があれば名指しで指摘する\n"
        "- 抽象名詞「〜性」、em ダッシュ、過度な絵文字は使わない。です/ます調。一人称は「自分」"
    )
    eng = engine if engine in DEFAULT_MODELS else "claude"
    try:
        out = call_ai(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            engine=eng,
            model=DEFAULT_MODELS[eng],
            max_tokens=600,
        )
    except Exception as e:
        out = f"(AI 生成失敗: {e})"

    return {
        "generated_at": now.isoformat(),
        "recommendation": out,
        "engine_used": eng,
        "context_counts": {
            "remaining_calendar": len(cal),
            "pending_emails": len(emails),
            "open_backlog": len(backlog),
            "tasks": len(tasks),
        },
    }


# ─── /triage ───
@router.get("/triage")
def triage(ai: bool = Query(False), engine: str = Query("claude")):
    emails = _pending_emails(20)
    backlog = _open_backlog(20)
    tasks = _overdue_tasks(20)

    result: dict = {
        "generated_at": now_jst().isoformat(),
        "emails": emails,
        "backlog": backlog,
        "overdue_tasks": [t for t in tasks if t.get("overdue")],
        "tasks": tasks,
        "counts": {
            "emails": len(emails),
            "backlog": len(backlog),
            "overdue_tasks": len([t for t in tasks if t.get("overdue")]),
        },
    }

    if ai:
        prompt = (
            "以下の『未対応』を全部見て、今週片付ける優先順位トップ10を作ってください。\n"
            "各項目: 『順位. [種別] 内容 — なぜ今か(1行)』。\n\n"
            f"=== 対応待ちメール ===\n{json.dumps(emails, ensure_ascii=False)}\n\n"
            f"=== バックログ ===\n{json.dumps(backlog, ensure_ascii=False)}\n\n"
            f"=== タスク ===\n{json.dumps(tasks, ensure_ascii=False)}\n"
        )
        system = (
            "あなたは志柿の秘書 AI。散らばった未対応を俯瞰し、現実的な優先順位をつける。"
            "締切・放置日数を根拠に。迎合せず、先送り常習のものは指摘する。"
            "抽象名詞「〜性」と em ダッシュは使わない。です/ます調。"
        )
        eng = engine if engine in DEFAULT_MODELS else "claude"
        try:
            result["ai_priorities"] = call_ai(
                messages=[{"role": "user", "content": prompt}],
                system=system,
                engine=eng,
                model=DEFAULT_MODELS[eng],
                max_tokens=900,
            )
            result["engine_used"] = eng
        except Exception as e:
            result["ai_priorities"] = f"(AI 生成失敗: {e})"

    return result


# ─── /ai-usage ───
@router.get("/ai-usage")
def ai_usage(days: int = Query(90, ge=1, le=3650)):
    # worklog ベース
    wl_by_engine: dict = {}
    wl_by_category: dict = {}
    try:
        from routers.work_log import work_log_stats
        st = work_log_stats(days)
        wl_by_engine = st.get("by_engine", {})
        wl_by_category = st.get("engine_by_category", {})
    except Exception:
        pass

    # routine 実行ベース
    run_by_engine: dict = {}
    try:
        from routers.routines import RUNS_FILE
        from data_manager import read_jsonl
        for r in read_jsonl(RUNS_FILE):
            eng = r.get("engine_used") or "?"
            run_by_engine[eng] = run_by_engine.get(eng, 0) + 1
    except Exception:
        pass

    return {
        "days": days,
        "worklog_by_engine": wl_by_engine,
        "worklog_engine_by_category": wl_by_category,
        "routine_runs_by_engine": run_by_engine,
    }


# ─── /assist/order : 早く片付けるべき順 (構造化) ───
@router.get("/assist/order")
def order(engine: str = Query("claude"), business: bool = Query(False)):
    """未対応を全部集約し、AI が『早く片付けるべき順』に並べて構造化して返す。

    フロントはこの1件を選んで /assist/plan に渡す想定。
    頭が混乱している時に『まずどれ』を迷わせないための入口。
    business=True の時だけ、利益・収益の視点を順位づけに足す (ビジネス相談モード)。
    """
    now = now_jst()
    cal = _todays_calendar(remaining_only=True)
    emails = _pending_emails(20)
    backlog = _open_backlog(20)
    tasks = _overdue_tasks(20)

    why_hint = "締切・放置日数を数字で" + ("、収益に効くなら一言" if business else "")
    prompt = (
        f"今は {now.strftime('%Y-%m-%d %H:%M (%A)')}。以下の散らばった未対応を全部見て、"
        "『早く片付けるべき順』に並べてください。最大10件。\n\n"
        f"=== 今日の残り予定 ===\n{json.dumps(cal, ensure_ascii=False)}\n\n"
        f"=== 対応待ちメール ===\n{json.dumps(emails, ensure_ascii=False)}\n\n"
        f"=== 未完バックログ ===\n{json.dumps(backlog, ensure_ascii=False)}\n\n"
        f"=== 期限つきタスク ===\n{json.dumps(tasks, ensure_ascii=False)}\n\n"
        "次の JSON だけを出力 (前後に地の文を書かない):\n"
        '{"items":[{"rank":1,"kind":"email|task|backlog","title":"内容(60字以内)",'
        f'"why":"なぜ今か({why_hint},1行)",'
        '"is_email":true,"payoff":"' + ("money|progress|obligation|none" if business else "progress|obligation|none") + '",'
        '"minutes":15}]}'
    )
    payoff_rule = (
        "- 少額でも利益・収益(収入/掲載/受注/納品)に効くものは順位を上げる。payoff に反映\n"
        if business else
        "- 順位の根拠は締切と放置日数だけ。利益や金の話は持ち出さない。payoff に money は使わない\n"
    )
    system = (
        "あなたは志柿の相棒 AI。散らばった未対応を俯瞰し『早く片付けるべき順』を決める。\n"
        "順位の付け方:\n"
        "- 締切の近さ・放置日数を最優先の根拠にする。数字を引く\n"
        + payoff_rule +
        "- 5分で終わる軽いものは、詰まって動けない時の突破口として上位に混ぜてよい\n"
        "- 迎合しない。先送り常習のものは why で名指しする\n"
        "- 抽象名詞「〜性」、em ダッシュは使わない。です/ます調"
    )
    eng = engine if engine in DEFAULT_MODELS else "claude"
    items: list[dict] = []
    err = None
    try:
        raw = call_ai(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            engine=eng,
            model=DEFAULT_MODELS[eng],
            max_tokens=1200,
        )
        parsed = _parse_json(raw)
        if isinstance(parsed, dict):
            items = parsed.get("items", []) or []
        elif isinstance(parsed, list):
            items = parsed
    except Exception as e:
        err = str(e)

    # AI が落ちても最低限は返す (放置日数 → 締切の素朴順)
    if not items:
        fallback = []
        for e in emails[:5]:
            fallback.append({"kind": "email", "title": e.get("subject", ""),
                             "why": f"放置 {e.get('days_since', 0)} 日", "is_email": True,
                             "payoff": "obligation", "minutes": 10})
        for t in [x for x in tasks if x.get("overdue")][:5]:
            fallback.append({"kind": "task", "title": t.get("title", ""),
                             "why": f"期限 {t.get('due_date')} 超過", "is_email": False,
                             "payoff": "obligation", "minutes": 20})
        for i, it in enumerate(fallback, 1):
            it["rank"] = i
        items = fallback

    return {
        "generated_at": now.isoformat(),
        "engine_used": eng,
        "items": items[:10],
        "counts": {
            "remaining_calendar": len(cal),
            "pending_emails": len(emails),
            "open_backlog": len(backlog),
            "overdue_tasks": len([t for t in tasks if t.get("overdue")]),
        },
        "error": err,
    }


# ─── /assist/plan : 1件を手順に分解 (詰まった時の一歩・文面) ───
class PlanReq(BaseModel):
    title: str
    kind: str = "auto"          # auto | email | task | backlog
    context: str = ""           # 相手・締切・状況など補足 (任意)
    is_email: bool | None = None
    business: bool = False       # ビジネス相談モード。True の時だけ利益の視点を足す
    engine: str = "claude"


@router.post("/assist/plan")
def plan(req: PlanReq):
    """選んだ1件を、そのまま動ける手順に分解して返す。

    - steps       : 最短手順 (詰まらない粒度の番号つき)
    - first_step  : どうしようもない時に、これだけやればいい最初の一歩
    - email_draft : メール系なら文面案 (志柿スタイル)
    - profit_angle: business=True の時だけ。この一手が利益・収益にどう効くか (それ以外は null)
    """
    now = now_jst()
    is_email = req.is_email
    if is_email is None:
        is_email = (req.kind == "email") or bool(
            re.search(r"メール|返信|連絡|問い合わせ|依頼|お礼|案内|催促", req.title)
        )

    prompt = (
        f"次の1件を、そのまま動ける手順に分解してください。\n\n"
        f"件名/内容: {req.title}\n"
        f"種別: {req.kind}\n"
        f"補足: {req.context or '(なし)'}\n"
        f"メール系か: {'はい' if is_email else 'いいえ'}\n\n"
        "次の JSON だけを出力 (前後に地の文を書かない):\n"
        "{\n"
        '  "first_step": "詰まって動けない時、これだけやればいい最初の一歩(1文,2分以内)",\n'
        '  "steps": ["手順1","手順2","..."],\n'
        '  "minutes": 30,\n'
        '  "watch_out": "詰まりやすい所や注意(1-2行)",\n'
        + ('  "profit_angle": "この一手が利益・収益にどう効くか(1-2行)",\n' if req.business else '')
        + ('  "email_draft": "そのまま送れる文面案(件名込み,志柿スタイル)"\n' if is_email else '  "email_draft": null\n')
        + "}"
    )
    profit_rule = (
        "- profit_angle は現実的に。少額でも前進なら正直に書く。効かないなら「直接の利益は薄い」と言う\n"
        if req.business else
        "- 利益や金の話は一切書かない。手順と一歩だけに集中する\n"
    )
    system = (
        "あなたは志柿の実務相棒 AI。頭が混乱している人でも順に動けるよう手順を切る。\n"
        "ルール:\n"
        "- steps は『考えずに手が動く』粒度。曖昧語(検討する等)は使わず、具体的な動作にする\n"
        "- first_step は本当に小さく。動き出せない時の突破口\n"
        + profit_rule +
        "- メール系は email_draft をそのまま送れる完成度で。相手が不明なら丁寧側に寄せる\n"
        "- 文体: です/ます調。一人称は「自分」。抽象名詞「〜性」・em ダッシュ・過度な絵文字は使わない\n"
        "- 迎合しない。盛らない"
    )
    eng = req.engine if req.engine in DEFAULT_MODELS else "claude"
    err = None
    parsed = None
    try:
        raw = call_ai(
            messages=[{"role": "user", "content": prompt}],
            system=system,
            engine=eng,
            model=DEFAULT_MODELS[eng],
            max_tokens=1400,
        )
        parsed = _parse_json(raw)
    except Exception as e:
        err = str(e)

    if not isinstance(parsed, dict):
        parsed = {
            "first_step": "まず件名を1行、白紙に書き出す",
            "steps": ["対象を1つに絞る", "5分だけ手を付ける", "できた所までで一旦切る"],
            "minutes": None,
            "watch_out": "(AI 分解に失敗しました。もう一度試してください)",
            "profit_angle": None,
            "email_draft": None,
        }

    return {
        "generated_at": now.isoformat(),
        "engine_used": eng,
        "title": req.title,
        "is_email": is_email,
        "first_step": parsed.get("first_step"),
        "steps": parsed.get("steps") or [],
        "minutes": parsed.get("minutes"),
        "watch_out": parsed.get("watch_out"),
        # ビジネス相談モードの時だけ利益の視点を返す。それ以外は必ず null
        "profit_angle": parsed.get("profit_angle") if req.business else None,
        "email_draft": parsed.get("email_draft"),
        "error": err,
    }


# ─── /assist/slots : 手順を入れられる空き時間の候補 ───
@router.get("/assist/slots")
def slots(minutes: int = Query(30, ge=15, le=480), days_ahead: int = Query(2, ge=0, le=7)):
    """指定分数が入る空きスロットを近い順で返す。フロントの『いつ入れる?』候補用。"""
    try:
        from routers.scheduling import _find_free_slots
        found = _find_free_slots(days_ahead=days_ahead, min_minutes=minutes)
    except Exception:
        found = []
    return {"generated_at": now_jst().isoformat(), "requested_minutes": minutes, "slots": found[:8]}


# ─── /assist/schedule : 手順を時間ブロックとして Calendar に確保 ───
class ScheduleReq(BaseModel):
    title: str
    minutes: int = 30
    steps: list[str] = []
    start_iso: str | None = None       # 指定なら固定。無ければ次の空きに自動確保
    first_step: str | None = None
    category: str = "default"


@router.post("/assist/schedule")
def schedule(req: ScheduleReq):
    """順番ナビで分解した手順を、実際に集中ブロックとして Google Calendar に書き込む。

    『見るだけ』で終わらせないための最後の一押し。手順は description に checklist として埋める。
    書き込みはこの明示操作でだけ起きる。
    """
    from gcal import create_event, is_configured
    if not is_configured():
        raise HTTPException(status_code=400, detail="calendar not configured")

    mins = max(15, min(req.minutes or 30, 480))

    # 開始時刻: 指定があればそれ、無ければ次の空きスロット
    start_iso = req.start_iso
    picked_slot = None
    if not start_iso:
        try:
            from routers.scheduling import _find_free_slots
            found = _find_free_slots(days_ahead=3, min_minutes=mins)
        except Exception:
            found = []
        if not found:
            raise HTTPException(status_code=409, detail="空きスロットが見つかりません。start_iso を指定してください")
        picked_slot = found[0]
        start_iso = picked_slot["start_iso"]

    try:
        start_dt = datetime.fromisoformat(start_iso)
    except Exception:
        raise HTTPException(status_code=400, detail=f"start_iso の形式が不正です: {start_iso}")
    end_dt = start_dt + timedelta(minutes=mins)

    # description に手順チェックリストを埋める
    lines = ["Koach OS 順番ナビが確保した集中ブロックです。動かして構いません。", ""]
    if req.first_step:
        lines += [f"▶ 詰まったらこれだけ: {req.first_step}", ""]
    if req.steps:
        lines.append("手順:")
        lines += [f"☐ {i}. {s}" for i, s in enumerate(req.steps, 1)]
    description = "\n".join(lines)

    try:
        ev = create_event(
            title=f"🧭 {req.title}",
            start_iso=start_dt.isoformat(),
            end_iso=end_dt.isoformat(),
            description=description,
            event_type="default",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"create_event failed: {e}")

    return {
        "ok": True,
        "start_iso": start_dt.isoformat(),
        "end_iso": end_dt.isoformat(),
        "minutes": mins,
        "auto_slot": picked_slot,
        "event": {
            "id": ev.get("id"),
            "html_link": ev.get("htmlLink") or ev.get("html_link"),
            "summary": ev.get("summary"),
        },
    }
