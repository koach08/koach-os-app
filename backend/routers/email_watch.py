"""
大学業務メール監視 + 対応遅延リマインダ。

POST /api/email-watch/scan?slot=2&days=30 — Gmail スキャン → AI 分類 → followups.json 更新
GET  /api/email-watch/pending              — 対応待ちのみ (snooze 除外、自分が返信済みは除外)
GET  /api/email-watch/all                  — 全件
POST /api/email-watch/{id}/done            — 対応済みマーク
POST /api/email-watch/{id}/snooze          — N 日 / 日付指定でリマインド延期
POST /api/email-watch/{id}/reopen          — 完了取消
"""

from __future__ import annotations

import json
import re
from datetime import date as date_cls, timedelta
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel

from data_manager import DATA_DIR, get_secret, now_jst, timestamp_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

FOLLOWUPS_FILE = DATA_DIR / "email_followups.json"


def _load() -> dict:
    if not FOLLOWUPS_FILE.exists():
        return {"items": {}, "updated_at": None}
    try:
        return json.loads(FOLLOWUPS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"items": {}, "updated_at": None}


def _write(data: dict):
    data["updated_at"] = timestamp_jst()
    FOLLOWUPS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _latest_sent_per_thread(slot: int, days: int = 90) -> dict[str, int]:
    """threadId → 自分が最後に送った internalDate (ms since epoch, int)。

    同じ thread で過去に別件で send していて、その後新しい受信が来た場合に
    誤って「対応済み」と判定するのを防ぐため、判定側で受信日と比較する。
    """
    try:
        from gcal import _get_gmail_service
        service = _get_gmail_service(slot)
    except Exception:
        return {}
    q = f"newer_than:{days}d in:sent"
    out: dict[str, int] = {}
    try:
        listing = service.users().messages().list(userId="me", q=q, maxResults=500).execute()
        refs = listing.get("messages", []) or []
        if not refs:
            return out
        BATCH = 50
        results: dict[str, dict] = {}

        def cb(rid, resp, exc):
            if exc is None and resp:
                results[rid] = resp

        for cs in range(0, len(refs), BATCH):
            chunk = refs[cs:cs + BATCH]
            batch = service.new_batch_http_request(callback=cb)
            for i, ref in enumerate(chunk):
                batch.add(
                    service.users().messages().get(
                        userId="me", id=ref["id"], format="minimal"
                    ),
                    request_id=f"{cs}_{i}",
                )
            try:
                batch.execute()
            except Exception:
                continue
        for r in results.values():
            tid = r.get("threadId")
            if not tid:
                continue
            try:
                ts = int(r.get("internalDate", "0"))
            except Exception:
                ts = 0
            if ts > out.get(tid, 0):
                out[tid] = ts
    except Exception:
        pass
    return out


def _received_ms(date_header: str) -> int:
    """email Date ヘッダから ms since epoch を取得。parse 不可なら 0。"""
    if not date_header:
        return 0
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_header)
        if dt is None:
            return 0
        return int(dt.timestamp() * 1000)
    except Exception:
        return 0


CLASSIFY_PROMPT = """あなたは志柿浩一郎 (北海道大学 准教授・kshigaki@imc.hokudai.ac.jp、kshgks59@gmail.com に転送) のメール仕分け担当。

各メールについて以下を判定し JSON 配列で返す:

[
  {
    "id": "(渡された ID をそのまま)",
    "category": "university | research | prospective_student | personal | promo | system | other",
    "requires_action": true | false,
    "urgency": "high | medium | low",
    "deadline_date": "YYYY-MM-DD or null (本文に締切が明示されていれば)",
    "summary": "20-40 字の日本語要約",
    "action_hint": "返信 / 提出 / 出席確認 / 情報のみ など 1〜2 語"
  }
]

判定ルール:
- **最優先**: From が hokudai.ac.jp / imc.hokudai.ac.jp ドメイン (北大全体) で **教員個人にアクションが要るもの** → category=university, requires_action=true 固定、urgency は medium 以上 (締切明示なら high)
- ただし北大ドメインでも、大学院入試 / ネット出願 / 募集要項 / 全学広報 / 学生向け案内 / 受験生向け配信のような「**多数配信・教員個人にアクション不要**」のものは category=promo, requires_action=false にしてよい (志柿は教員、出願ではなく出題側)
- **prospective_student**: 大学院 (修士・博士) 進学希望者 / 研究室訪問希望 / 指導教員相談 / Ph.D. inquiry / graduate admission の個人的問い合わせ → 必ず requires_action=true, urgency は medium 以上。 件名/本文に「進学希望」「研究室訪問」「指導教員」「修士課程」「博士課程」「博士後期」「大学院」「Ph.D.」「PhD」「graduate program」「research interest」「admission inquiry」を含み、かつ送信者が学生 (elms.hokudai / 他大学学生メアド / Gmail 個人) のもの
- university: 学部・授業・委員会・学生関係・大学事務・北大関連 → 基本 requires_action=true
- research: 他大学 (.ac.jp / .edu) の教員・共著者・査読・学会・科研費 → 業務連絡 (日程相談 / 会議調整 / 共同研究 / 論文相談 / 学生指導) なら requires_action=true。純粋な情報共有のみ false
- promo: ニュースレター・広告・配信通知 (mailmag / no-reply / news@) → requires_action=false
- system: 自動通知 (パスワードリセット / OAuth / GitHub PR 通知) → requires_action=false
- personal: 家族・友人・サブスク管理 → 文脈次第
- 「先生」「教授」「准教授」「博士」が From に入る人間のメール、または件名に「ご相談」「日程」「会議」「お打ち合わせ」「ご依頼」「ご確認」「お願い」を含む → requires_action=true
- urgency: deadline_date があれば high。明確な締切表現 (締切 / までに / 〆切 / 期日) → medium 以上
- summary: です/ます調禁止、体言止め可、抽象名詞「〜性」NG

JSON のみ。Markdown 禁止。"""


_HOKUDAI_DOMAINS = ("hokudai.ac.jp", "imc.hokudai.ac.jp")
_AUTO_SENDER_PATTERNS = (
    "no-reply", "noreply", "no_reply", "do-not-reply", "donotreply", "do_not_reply",
    "notifications@", "notification@", "news@", "newsletter", "mailmag",
    "mailer-daemon", "postmaster@", "alerts@", "info@",
)
# 大学・研究機関ドメイン (.ac.jp / .edu / .ac.<cc> / 国立研究機関)
_ACADEMIC_DOMAIN_PATTERNS = (".ac.jp", ".edu", ".ac.kr", ".ac.uk", ".ac.cn", ".edu.tw", "riken.jp", "nii.ac.jp", "jaxa.jp")


def _is_hokudai(from_field: str) -> bool:
    """From フィールドに北大ドメインが含まれるか"""
    if not from_field:
        return False
    f = from_field.lower()
    return any(d in f for d in _HOKUDAI_DOMAINS)


def _is_auto_sender(from_field: str) -> bool:
    """自動配信っぽい From かを判定 (no-reply 等)"""
    if not from_field:
        return False
    f = from_field.lower()
    return any(p in f for p in _AUTO_SENDER_PATTERNS)


def _is_academic_sender(from_field: str) -> bool:
    """大学・研究機関ドメインからか (北大含む)"""
    if not from_field:
        return False
    f = from_field.lower()
    return any(d in f for d in _ACADEMIC_DOMAIN_PATTERNS)


_PROSPECTIVE_KEYWORDS = (
    "進学希望", "研究室訪問", "指導教員", "修士課程", "博士課程", "博士後期",
    "大学院進学", "院進学", "phd", "ph.d", "graduate program", "research interest",
    "admission inquiry", "research student", "院試", "受験希望", "大学院入学",
)


def _is_prospective_keyword(subject: str, snippet: str) -> bool:
    """件名・snippet に進学希望者キーワードが含まれるか"""
    text = ((subject or "") + " " + (snippet or "")).lower()
    return any(k in text for k in _PROSPECTIVE_KEYWORDS)


class ScanReq(BaseModel):
    slot: int = 2
    days: int = 30
    max_emails: int = 150
    engine: str = "gpt"


def _classify_batch(emails: list[dict], engine: str) -> list[dict]:
    """AI に分類を 1 リクエストでまとめて投げる。"""
    if not emails:
        return []
    batch_text = "\n\n".join(
        f"---\nID: {e['id']}\nFrom: {e.get('from','')}\nSubject: {e.get('subject','')}\nSnippet: {e.get('snippet','')[:300]}\nBody (excerpt): {e.get('body','')[:600]}"
        for e in emails
    )
    user_msg = f"以下 {len(emails)} 件のメールを分類してください:\n\n{batch_text}"
    if engine not in DEFAULT_MODELS:
        engine = "gpt"
    model = DEFAULT_MODELS[engine]
    try:
        raw = call_ai(
            messages=[{"role": "user", "content": user_msg}],
            system=CLASSIFY_PROMPT,
            engine=engine,
            model=model,
            max_tokens=4000,
        )
    except Exception as e:
        raise HTTPException(500, f"AI classify failed: {e}")
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        # 救出: 最初の [ から最後の ] まで
        m = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return []
        return []


_SCAN_STATUS: dict = {
    "running": False,
    "started_at": None,
    "finished_at": None,
    "result": None,
    "error": None,
}


def _run_scan_bg(req: ScanReq):
    try:
        result = _do_scan(req)
        _SCAN_STATUS.update(
            {"running": False, "finished_at": timestamp_jst(), "result": result, "error": None}
        )
    except Exception as e:
        _SCAN_STATUS.update(
            {"running": False, "finished_at": timestamp_jst(), "error": str(e)}
        )


@router.post("/email-watch/scan")
def scan(req: ScanReq, background_tasks: BackgroundTasks):
    """重い処理 (100 秒超) なので即時応答 → バックグラウンド実行。
    結果は GET /email-watch/scan-status でポーリングする。
    (同期実行だと Vercel の中継が先にタイムアウトし ROUTER_EXTERNAL_TARGET_ERROR になっていた)"""
    from gcal import is_configured
    if not is_configured():
        raise HTTPException(400, "Google integration not configured")
    if _SCAN_STATUS.get("running"):
        return {"ok": True, "started": False, "already_running": True}
    _SCAN_STATUS.update(
        {"running": True, "started_at": timestamp_jst(), "finished_at": None, "result": None, "error": None}
    )
    background_tasks.add_task(_run_scan_bg, req)
    return {"ok": True, "started": True}


@router.get("/email-watch/scan-status")
def scan_status():
    return _SCAN_STATUS


def _do_scan(req: ScanReq) -> dict:
    from gcal import list_recent_emails
    try:
        emails = list_recent_emails(days=req.days, max_results=req.max_emails, slot=req.slot)
    except Exception as e:
        raise HTTPException(500, f"Gmail fetch failed: {e}")

    state = _load()
    items: dict = state.get("items", {}) or {}
    latest_sent = _latest_sent_per_thread(req.slot, days=max(60, req.days * 2))

    def _is_replied_after_receive(thread_id: str, received_at: str) -> bool:
        """その thread に対して、受信後に自分が send したメッセージがあるか。"""
        if not thread_id or thread_id not in latest_sent:
            return False
        recv_ms = _received_ms(received_at)
        if recv_ms == 0:
            # 受信日 parse 不可なら従来通り「同 thread に sent あり = 返信済み」と扱う (false positive 残るが安全側)
            return True
        # 受信より後の sent があれば返信済み (1 分マージン)
        return latest_sent[thread_id] > recv_ms + 60_000

    # 既存 followups の済み判定を再評価:
    # - done_reason が "manual" のものは触らない (人間の意思)
    # - auto 系で done になっているが、新ロジックで該当しないものは done を解除 (旧ロジックの誤判定救済)
    # - まだ done でないが受信後 sent があるものは done に
    for fid, fp in items.items():
        reason = fp.get("done_reason") or ""
        replied_after = _is_replied_after_receive(fp.get("thread_id", ""), fp.get("received_at", ""))
        if fp.get("done_at"):
            if reason.startswith("auto") and not replied_after:
                fp["done_at"] = None
                fp["done_reason"] = None
        else:
            if replied_after:
                fp["done_at"] = timestamp_jst()
                fp["done_reason"] = "auto: 返信済み (sent items 検出, 受信後)"

    # 新規メールのみ classify
    new_emails = [e for e in emails if e["id"] not in items]
    BATCH_SIZE = 20
    classified: list[dict] = []
    for i in range(0, len(new_emails), BATCH_SIZE):
        chunk = new_emails[i:i + BATCH_SIZE]
        try:
            classified.extend(_classify_batch(chunk, req.engine))
        except Exception:
            continue
    cls_by_id = {c.get("id", ""): c for c in classified if c.get("id")}

    added = 0
    for e in new_emails:
        c = cls_by_id.get(e["id"])
        if not c:
            continue
        category = c.get("category", "other")
        requires_action = bool(c.get("requires_action"))
        urgency = c.get("urgency", "medium")

        from_field = e.get("from", "")
        is_hokudai = _is_hokudai(from_field)
        is_academic = _is_academic_sender(from_field)
        is_auto = _is_auto_sender(from_field)
        is_prospective = _is_prospective_keyword(e.get("subject", ""), e.get("snippet", ""))

        # 進学希望者キーワード検出 → 強制 prospective_student (auto sender は除く)
        if is_prospective and not is_auto and category not in ("promo", "system"):
            category = "prospective_student"
            requires_action = True
            if urgency == "low":
                urgency = "medium"

        # 北大ドメインは強制で要対応 (ただし AI が promo/system と判定したものは尊重 → 学生向け全体配信などはノイズ)
        if is_hokudai and category not in ("promo", "system", "prospective_student"):
            category = "university"
            requires_action = True
            if urgency == "low":
                urgency = "medium"

        # 他大学・研究機関 (.ac.jp / .edu 等) の **人間** からのメールは強制保存 + 要対応
        # (AI が research+requires_action=false にしたケースを救済 — 日程相談・会議調整など漏らさない)
        if is_academic and not is_hokudai and not is_auto and category not in ("promo", "system", "prospective_student"):
            requires_action = True
            if category == "other":
                category = "research"

        # promo / system は捨てる (自動配信・学生向け広報なので)
        if category in ("promo", "system"):
            continue
        # それ以外は requires_action=true のみ保存。
        # ただし category=university (北大) は requires_action 無視で常に保存
        if category != "university" and not requires_action:
            continue

        item = {
            "id": e["id"],
            "thread_id": e.get("thread_id", ""),
            "from": e.get("from", ""),
            "subject": e.get("subject", "(no subject)"),
            "received_at": e.get("date", ""),
            "snippet": e.get("snippet", "")[:300],
            "category": category,
            "urgency": urgency,
            "deadline_date": c.get("deadline_date"),
            "summary": c.get("summary", ""),
            "action_hint": c.get("action_hint", ""),
            "slot": req.slot,
            "scanned_at": timestamp_jst(),
            "done_at": None,
            "snooze_until": None,
        }
        # 受信日より後に同 thread で自分が送っていたら done
        if _is_replied_after_receive(item["thread_id"], item["received_at"]):
            item["done_at"] = timestamp_jst()
            item["done_reason"] = "auto: 返信済み (受信後 sent)"
        items[item["id"]] = item
        added += 1

    state["items"] = items
    _write(state)

    return {
        "ok": True,
        "scanned": len(emails),
        "new_classified": len(classified),
        "added_followups": added,
        "total_tracked": len(items),
    }


def _is_pending(it: dict, today: str, overdue_days: int = 2) -> bool:
    if it.get("done_at"):
        return False
    if it.get("snooze_until") and it["snooze_until"] > today:
        return False
    return True


def _days_since(received_at: str) -> int:
    """email Date ヘッダから経過日数を計算 (parse できない場合は 0)。"""
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(received_at)
        if dt is None:
            return 0
        delta = now_jst() - dt
        return max(0, delta.days)
    except Exception:
        return 0


@router.get("/email-watch/pending")
def list_pending(overdue_only: bool = Query(False), overdue_days: int = Query(2)):
    state = _load()
    today = now_jst().strftime("%Y-%m-%d")
    out = []
    for it in (state.get("items", {}) or {}).values():
        if not _is_pending(it, today):
            continue
        days_old = _days_since(it.get("received_at", ""))
        if overdue_only and days_old < overdue_days:
            continue
        enriched = {**it, "days_since_received": days_old}
        out.append(enriched)
    URGENCY_RANK = {"high": 0, "medium": 1, "low": 2}
    out.sort(
        key=lambda x: (
            URGENCY_RANK.get(x.get("urgency", "medium"), 1),
            -x.get("days_since_received", 0),
        )
    )
    return {"items": out, "count": len(out)}


@router.get("/email-watch/all")
def list_all(limit: int = Query(100)):
    state = _load()
    items = list((state.get("items", {}) or {}).values())
    items.sort(key=lambda x: x.get("received_at", ""), reverse=True)
    return {"items": items[:limit], "count": len(items)}


@router.post("/email-watch/{item_id}/done")
def mark_done(item_id: str):
    state = _load()
    items = state.get("items", {}) or {}
    if item_id not in items:
        raise HTTPException(404, "not found")
    items[item_id]["done_at"] = timestamp_jst()
    items[item_id]["done_reason"] = "manual"
    _write(state)
    return items[item_id]


@router.post("/email-watch/{item_id}/reopen")
def reopen(item_id: str):
    state = _load()
    items = state.get("items", {}) or {}
    if item_id not in items:
        raise HTTPException(404, "not found")
    items[item_id]["done_at"] = None
    items[item_id]["done_reason"] = None
    _write(state)
    return items[item_id]


class SnoozeReq(BaseModel):
    days: int | None = None
    date: str | None = None
    clear: bool = False


@router.post("/email-watch/{item_id}/snooze")
def snooze(item_id: str, body: SnoozeReq):
    state = _load()
    items = state.get("items", {}) or {}
    if item_id not in items:
        raise HTTPException(404, "not found")
    if body.clear:
        items[item_id]["snooze_until"] = None
    elif body.date:
        items[item_id]["snooze_until"] = body.date
    elif body.days is not None:
        items[item_id]["snooze_until"] = (now_jst().date() + timedelta(days=max(0, body.days))).isoformat()
    else:
        raise HTTPException(400, "days か date か clear が必要")
    _write(state)
    return items[item_id]


# ---------------------------------------------------------------------------
# 返信案 AI 相談 — POST /email-watch/{item_id}/draft-reply
# ---------------------------------------------------------------------------

DRAFT_REPLY_SYSTEM = """あなたは志柿浩一郎 (北海道大学 メディア・観光学院 准教授) の代理メール起案担当。

返信案を作る時のルール:
- 件名は元の Subject に Re: を付ける (既に Re: なら維持)
- 宛名は元の From の名前を「○○様 (or 先生)」で
- 敬語は「です・ます」調。 ただし冗長な敬語連打は避け、 1 文 60 字以内基準
- 「いつも大変お世話になっております」等の定型挨拶は学外の人にのみ。 学内事務には不要
- 学外の研究者宛 → 1 文目で謝意、 2 文目で本題、 締切や日程相談なら具体日 / 候補日まで踏み込む
- 学生宛 → 簡潔に、 余計な感情表現なし、 必要なら添付物・期限を明示
- 不明な点 (具体日時・添付の有無等) は本文中に [(志柿が記入: ...)] のプレースホルダで残す
- 抽象名詞「〜性」、 感情を煽る表現、 過度な絵文字は使わない
- 末尾の署名:
    志柿浩一郎
    北海道大学 大学院メディア・コミュニケーション研究院

ユーザーからヒントが渡されていれば、 その内容を最優先で反映する。

出力フォーマット:
件名: <件名>

<本文>

JSON や Markdown 装飾は不要。本文プレーンテキスト。"""


class DraftReplyReq(BaseModel):
    hint: str | None = None
    engine: str = "claude"


@router.post("/email-watch/{item_id}/draft-reply")
def draft_reply(item_id: str, body: DraftReplyReq):
    state = _load()
    items = state.get("items", {}) or {}
    item = items.get(item_id)
    if not item:
        raise HTTPException(404, "not found")

    # フル本文を Gmail から取得 (snippet だけだと足りない事が多い)
    full_body = ""
    try:
        from gcal import _get_gmail_service
        service = _get_gmail_service(item.get("slot", 2))
        msg = service.users().messages().get(userId="me", id=item_id, format="full").execute()
        full_body = _extract_plain_body(msg)
    except Exception:
        full_body = item.get("snippet", "")

    context = (
        f"=== 元メール ===\n"
        f"From: {item.get('from', '')}\n"
        f"件名: {item.get('subject', '')}\n"
        f"受信日: {item.get('received_at', '')}\n"
        f"要約: {item.get('summary', '')}\n"
        f"アクション目安: {item.get('action_hint', '')}\n"
        f"本文:\n{full_body[:4000]}\n"
    )
    if body.hint:
        context += f"\n=== ユーザーヒント ===\n{body.hint}\n"

    engine = body.engine if body.engine in DEFAULT_MODELS else "claude"
    model = DEFAULT_MODELS[engine]
    try:
        reply_text = call_ai(
            messages=[{"role": "user", "content": context + "\n返信案をプレーンテキストで起案してください。"}],
            system=DRAFT_REPLY_SYSTEM,
            engine=engine,
            model=model,
            max_tokens=2000,
        )
    except Exception as e:
        raise HTTPException(500, f"AI draft failed: {e}")

    return {
        "ok": True,
        "engine": engine,
        "model": model,
        "reply_text": reply_text.strip(),
        "chars": len(reply_text),
    }


def _extract_plain_body(msg: dict) -> str:
    """Gmail API の messages.get(format=full) から text/plain 本文を抽出"""
    import base64

    def walk(part: dict) -> str:
        mime = part.get("mimeType", "")
        body = part.get("body", {}) or {}
        data = body.get("data")
        if mime == "text/plain" and data:
            try:
                return base64.urlsafe_b64decode(data.encode("ascii") + b"==").decode("utf-8", errors="replace")
            except Exception:
                return ""
        for sub in part.get("parts", []) or []:
            t = walk(sub)
            if t:
                return t
        # text/html しかない場合の fallback
        if mime == "text/html" and data:
            try:
                html = base64.urlsafe_b64decode(data.encode("ascii") + b"==").decode("utf-8", errors="replace")
                # 簡易タグ除去
                return re.sub(r"<[^>]+>", " ", html)
            except Exception:
                return ""
        return ""

    payload = msg.get("payload") or {}
    return walk(payload).strip()
