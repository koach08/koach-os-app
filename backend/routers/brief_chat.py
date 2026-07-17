"""
Worklog Phase B-2 — Daily / Evening brief の「対話化」レイヤー (追加のみ・既存非干渉)

- POST /api/brief/chat        : brief を往復対話にする。「それは無理」「並べ替えて」に AI が応じ、
                                今日の組み方を調整する。忖度しない二段生成 (生成 → Haiku で褒め/煽り/
                                抽象名詞「〜性」を削る)。
- GET  /api/brief/continuity  : 「昨日 (直近) やっていたこと → 今日は?」の連続性データ。
                                completions.jsonl を主軸に、work_log を補助として束ねる。

既存の /api/daily-brief /api/evening-brief は一切変更しない。ここは新規ルーターの追加のみ。
"""

from __future__ import annotations

from datetime import timedelta
from fastapi import APIRouter
from pydantic import BaseModel

from data_manager import now_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

# 二段目 (褒め削り) は低コストの Haiku 固定
_CRITIC_MODEL = "claude-haiku-4-5"


# ---------------------------------------------------------------------------
# 連続性: completions 中心 + work_log 補助
# ---------------------------------------------------------------------------

def _recent_activity(days_back: int = 3) -> dict:
    """今日を除く直近 days_back 日の「やり遂げたこと」を集約。

    主軸は completions.jsonl (実データが溜まっている)、work_log は補助。
    戻り値: {"days": [{"date","label","items":[...]}...], "work_log":[...], "text": str}
    """
    now = now_jst()
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    cutoff = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")

    # 1. completions (主軸)
    comp_by_date: dict[str, list[str]] = {}
    try:
        from routers.completions import _current_state
        for (_kind, _ref, d), v in _current_state().items():
            if not d or d >= today or d < cutoff:
                continue
            title = (v.get("title") or "").strip() or "(無題)"
            comp_by_date.setdefault(d, []).append(title)
    except Exception:
        pass

    # 2. work_log (補助)
    work_recent: list[dict] = []
    try:
        from routers.work_log import _materialize
        for w in _materialize().values():
            d = w.get("date", "")
            if not d or d >= today or d < cutoff:
                continue
            work_recent.append(
                {
                    "date": d,
                    "title": (w.get("title") or "").strip(),
                    "category": w.get("category", ""),
                    "engine": w.get("engine", ""),
                    "outcome": (w.get("outcome") or "").strip(),
                }
            )
        work_recent.sort(key=lambda x: x["date"], reverse=True)
    except Exception:
        pass

    # 日付ごとに新しい順で整形
    days_out: list[dict] = []
    for d in sorted(comp_by_date.keys(), reverse=True):
        label = "昨日" if d == yesterday else d
        days_out.append({"date": d, "label": label, "items": comp_by_date[d][:12]})

    # AI 文脈用のテキスト要約
    lines: list[str] = []
    if days_out:
        for day in days_out[:days_back]:
            joined = " / ".join(day["items"][:8])
            lines.append(f"- {day['label']}: {joined}")
    if work_recent:
        lines.append("(実績台帳より)")
        for w in work_recent[:6]:
            tag = f"[{w['category']}]" if w["category"] else ""
            eng = f" ({w['engine']})" if w["engine"] else ""
            lines.append(f"- {w['date']} {tag}{w['title']}{eng}")
    text = "\n".join(lines) if lines else "(直近の完了ログなし)"

    return {"days": days_out, "work_log": work_recent, "text": text}


@router.get("/brief/continuity")
def brief_continuity(days_back: int = 3):
    """「昨日やっていたこと → 今日は?」の連続性データ。フロントの対話パネル冒頭に出す。"""
    act = _recent_activity(days_back=days_back)
    yesterday = (now_jst() - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterday_items: list[str] = []
    for day in act["days"]:
        if day["date"] == yesterday:
            yesterday_items = day["items"]
            break
    return {
        "generated_at": now_jst().isoformat(),
        "yesterday": yesterday_items,
        "recent_days": act["days"],
        "work_log_recent": act["work_log"],
        "has_history": bool(act["days"] or act["work_log"]),
        # 対話の口火。データが薄くても質問自体は成立する
        "seed_question": "昨日の続きで今日やることはありますか? それとも今日は別の山からですか?",
    }


# ---------------------------------------------------------------------------
# 対話: brief を往復にする + 忖度しない二段生成
# ---------------------------------------------------------------------------

class BriefChatIn(BaseModel):
    mode: str = "daily"            # daily | evening
    messages: list[dict] = []       # [{"role":"user"|"assistant","content":str}, ...]
    engine: str = "claude"


def _daily_context() -> str:
    """今日の予定 / オープンタスク / バックログ / 今日の完了 を圧縮したテキスト。"""
    now = now_jst()
    today = now.strftime("%Y-%m-%d")
    parts: list[str] = []

    # 予定
    try:
        from gcal import is_configured, get_events
        if is_configured():
            evs = get_events(days_ahead=0)
            sched = "\n".join(
                f"- {(e.get('start') or '')[11:16] or '終日'} {e.get('summary','(無題)')}"
                + (f" @ {e.get('location')}" if e.get("location") else "")
                for e in evs
            ) or "(予定なし)"
        else:
            sched = "(カレンダー未接続)"
    except Exception:
        sched = "(予定取得失敗)"
    parts.append(f"## 今日の予定\n{sched}")

    # オープンタスク
    try:
        from routers.daily_brief import _open_tasks
        tasks = _open_tasks()
        ttext = "\n".join(
            f"- [{t['priority']}] {t['title']}"
            + (f" (期限 {t['due_date']})" if t.get("due_date") else "")
            for t in tasks
        ) or "(オープンなタスクなし)"
    except Exception:
        ttext = "(タスク取得失敗)"
    parts.append(f"## オープンタスク\n{ttext}")

    # バックログ
    try:
        from routers.productivity import _load_backlog
        bl = [
            b for b in _load_backlog()
            if not b.get("done") and (not b.get("defer_until") or b["defer_until"] <= today)
        ]
        btext = "\n".join(
            f"- [{b.get('urgency','medium')}] [{b.get('category','other')}] {b.get('title','')}"
            f" (推定{b.get('estimated_minutes',60)}分)"
            for b in bl[:15]
        ) or "(バックログ空)"
    except Exception:
        btext = "(バックログ取得失敗)"
    parts.append(f"## Coach バックログ\n{btext}")

    # 今日の完了
    try:
        from routers.completions import _current_state
        done = [v for (_k, _r, d), v in _current_state().items() if d == today]
        done.sort(key=lambda x: x.get("completed_at", ""))
        dtext = "\n".join(f"- {c.get('title','')}" for c in done) or "(今日まだ完了なし)"
    except Exception:
        dtext = "(完了ログ取得失敗)"
    parts.append(f"## 今日すでに完了\n{dtext}")

    return "\n\n".join(parts)


def _evening_context() -> str:
    """今日の完了 / 取りこぼし / バックログ残 / 明日の予定 を圧縮したテキスト。"""
    now = now_jst()
    today = now.strftime("%Y-%m-%d")
    parts: list[str] = []

    try:
        from routers.completions import _current_state
        done = [v for (_k, _r, d), v in _current_state().items() if d == today]
        done.sort(key=lambda x: x.get("completed_at", ""))
        done_ids = {c.get("ref_id") for c in done if c.get("kind") == "calendar"}
        dtext = "\n".join(f"- {c.get('title','')}" for c in done) or "(今日は完了ログなし)"
    except Exception:
        done_ids = set()
        dtext = "(完了ログ取得失敗)"
    parts.append(f"## 今日完了したこと\n{dtext}")

    # 取りこぼし + 明日
    try:
        from gcal import is_configured, get_events
        if is_configured():
            missed = [
                e.get("summary", "")
                for e in get_events(days_ahead=0)
                if e.get("id") and e.get("id") not in done_ids
            ]
            mtext = "\n".join(f"- {m}" for m in missed[:8]) or "(取りこぼしなし)"
            tomo = get_events(days_ahead=1)
            ttext = "\n".join(
                f"- {(e.get('start') or '')[11:16] or '終日'} {e.get('summary','')}" for e in tomo[:8]
            ) or "(明日の予定なし)"
        else:
            mtext, ttext = "(カレンダー未接続)", "(カレンダー未接続)"
    except Exception:
        mtext, ttext = "(取得失敗)", "(取得失敗)"
    parts.append(f"## 予定で取りこぼしたもの\n{mtext}")

    try:
        from routers.productivity import _load_backlog
        bl = [b for b in _load_backlog() if not b.get("done")]
        btext = "\n".join(
            f"- [{b.get('urgency','medium')}] {b.get('title','')}" for b in bl[:10]
        ) or "(バックログ残なし)"
    except Exception:
        btext = "(取得失敗)"
    parts.append(f"## バックログ残り\n{btext}")
    parts.append(f"## 明日の予定\n{ttext}")

    return "\n\n".join(parts)


_STYLE = (
    "口調は です/ます。淡々と。一人称は「自分」。抽象名詞「〜性」「重要性」「必要性」は使わない。"
    "感情を煽らない。褒めるのは事実だけを1回。"
)


def _system_prompt(mode: str, continuity: str, context: str) -> str:
    now = now_jst()
    if mode == "evening":
        role = (
            "一日の終わりの振り返りを一緒にする。今日の動きを踏まえ、明日に繰り越すもの・落とすものを"
            "本人と会話しながら決める。"
        )
    else:
        role = (
            "朝、今日の一日の組み方を本人と一緒に決める。予定の隙間に何を入れるか、順番をどうするかを"
            "会話しながら詰める。本人が『それは無理』『先に別のをやりたい』と言えば、素直に組み直す。"
        )
    return f"""あなたは Koach OS。志柿の reflective partner。今は {now.strftime('%Y-%m-%d %H:%M (%A)')}。
{role}

## 直近やっていたこと (連続性)
{continuity}

## 今の状況
{context}

## 進め方
- 本人の発言に具体的に応じる。並べ替えを頼まれたら、時間帯つきの順番を短く提案する (例: 10:00-11:30 ○○)。
- 賛成しかしないのは禁止。無理がある案には無理だと言う。抜けている前提があれば1つだけ問い返す。
- 説教しない。長くしない。3〜5行。箇条書き可。
- {_STYLE}"""


def _critique(text: str) -> str:
    """二段目: 褒め/煽り/抽象名詞/AI 臭い定型を削り、志柿スタイルに寄せる。内容は足さない。"""
    critic_system = (
        "あなたは日本語の編集者。渡された返答から次を削る/直すだけを行う。新しい主張・提案・情報は"
        "一切足さない。並べ替え案や時間帯などの中身は必ず残す。\n"
        "削る/直す対象: おだて・空虚な称賛・煽り文句・AI 臭い定型 (『お役に立てれば』等)・"
        "抽象名詞「〜性」「重要性」「必要性」・過剰な前置き。\n"
        f"文体: {_STYLE}\n"
        "出力は本文だけ。前置きや説明を付けない。"
    )
    try:
        cleaned = call_ai(
            messages=[{"role": "user", "content": text}],
            system=critic_system,
            engine="claude",
            model=_CRITIC_MODEL,
            max_tokens=700,
        )
        cleaned = (cleaned or "").strip()
        return cleaned or text
    except Exception:
        return text


@router.post("/brief/chat")
def brief_chat(payload: BriefChatIn):
    mode = payload.mode if payload.mode in ("daily", "evening") else "daily"
    engine = payload.engine if payload.engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS[engine]

    continuity = _recent_activity(days_back=3)["text"]
    context = _evening_context() if mode == "evening" else _daily_context()
    system = _system_prompt(mode, continuity, context)

    # 会話履歴。空なら口火のユーザー発話を補う
    messages = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in payload.messages
        if m.get("content")
    ]
    if not messages:
        seed = (
            "今日の一日、どう組むのがいいか一緒に考えたいです。"
            if mode == "daily"
            else "今日の振り返りと、明日に繰り越すものを一緒に整理したいです。"
        )
        messages = [{"role": "user", "content": seed}]

    # 一段目
    try:
        draft = call_ai(messages=messages, system=system, engine=engine, model=model, max_tokens=700)
    except Exception as e:
        return {"reply": f"(対話生成に失敗: {e})", "engine_used": engine, "critiqued": False}

    # 二段目 (忖度削り)
    reply = _critique(draft)

    return {
        "reply": reply,
        "engine_used": engine,
        "model_used": model,
        "critiqued": reply != draft,
    }
