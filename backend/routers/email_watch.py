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

from fastapi import APIRouter, HTTPException, Query
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


def _replied_thread_ids(slot: int, days: int = 90) -> set[str]:
    """自分が send / 既に reply したスレッドの threadId 集合。"""
    try:
        from gcal import _get_gmail_service
        service = _get_gmail_service(slot)
    except Exception:
        return set()
    q = f"newer_than:{days}d in:sent"
    out: set[str] = set()
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
            if tid:
                out.add(tid)
    except Exception:
        pass
    return out


CLASSIFY_PROMPT = """あなたは志柿浩一郎 (北海道大学 准教授・kshigaki@imc.hokudai.ac.jp、kshgks59@gmail.com に転送) のメール仕分け担当。

各メールについて以下を判定し JSON 配列で返す:

[
  {
    "id": "(渡された ID をそのまま)",
    "category": "university | research | personal | promo | system | other",
    "requires_action": true | false,
    "urgency": "high | medium | low",
    "deadline_date": "YYYY-MM-DD or null (本文に締切が明示されていれば)",
    "summary": "20-40 字の日本語要約",
    "action_hint": "返信 / 提出 / 出席確認 / 情報のみ など 1〜2 語"
  }
]

判定ルール:
- university: 学部・授業・委員会・学生関係・大学事務・北大ドメイン全般 → 基本 requires_action=true
- research: 共著者・査読・学会・科研費 → requires_action は文脈次第
- promo: ニュースレター・広告・通知 → requires_action=false
- system: 自動通知 (パスワードリセット / OAuth) → requires_action=false
- personal: 家族・友人・サブスク管理 → 文脈次第
- requires_action: 返信や行動 (出席登録 / 提出 / 確認応答) が必要か
- urgency: deadline_date があれば high。明確な締切表現 (締切 / までに / 〆切) → medium 以上
- summary: です/ます調禁止、体言止め可、抽象名詞「〜性」NG

JSON のみ。Markdown 禁止。"""


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


@router.post("/email-watch/scan")
def scan(req: ScanReq):
    from gcal import is_configured, list_recent_emails
    if not is_configured():
        raise HTTPException(400, "Google integration not configured")

    try:
        emails = list_recent_emails(days=req.days, max_results=req.max_emails, slot=req.slot)
    except Exception as e:
        raise HTTPException(500, f"Gmail fetch failed: {e}")

    state = _load()
    items: dict = state.get("items", {}) or {}
    replied = _replied_thread_ids(req.slot, days=max(60, req.days * 2))

    # まず thread_id ベースで既存 followups の済みマーク
    for fid, fp in items.items():
        tid = fp.get("thread_id")
        if tid and tid in replied and not fp.get("done_at"):
            fp["done_at"] = timestamp_jst()
            fp["done_reason"] = "auto: 返信済み (sent items 検出)"

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
        # university / research / personal で requires_action なものだけ保存 (promo / system は捨てる)
        if not c.get("requires_action"):
            continue
        if c.get("category") in ("promo", "system"):
            continue
        item = {
            "id": e["id"],
            "thread_id": e.get("thread_id", ""),
            "from": e.get("from", ""),
            "subject": e.get("subject", "(no subject)"),
            "received_at": e.get("date", ""),
            "snippet": e.get("snippet", "")[:300],
            "category": c.get("category", "other"),
            "urgency": c.get("urgency", "medium"),
            "deadline_date": c.get("deadline_date"),
            "summary": c.get("summary", ""),
            "action_hint": c.get("action_hint", ""),
            "slot": req.slot,
            "scanned_at": timestamp_jst(),
            "done_at": None,
            "snooze_until": None,
        }
        # 既に返信済みならその場で済み
        if item["thread_id"] in replied:
            item["done_at"] = timestamp_jst()
            item["done_reason"] = "auto: 返信済み"
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
