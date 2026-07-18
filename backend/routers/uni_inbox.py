"""
大学メール受信箱 (University Inbox) — hokudai / ac.jp から来た予定・締切を「見落とさない」トラッカー。

課題: これまで Gmail 抽出も秘書も「その場で読み込む→提案止まり」で、処理済み/未処理の
状態を持たなかった。だから (1) 見落とし防止 も (2) 忘れていませんか のリマインド も
原理的にできなかった。この受信箱は抽出結果を 1 件ずつ状態管理する:

    pending (未反映) → calendared (カレンダー反映済) | dismissed (無視)

拾った項目は反映か無視をするまで pending で残り続ける = 取りこぼさない保証。
既に Google Calendar にある予定 (手動で入れた等) は scan 時に calendared 扱いにして二重通知を防ぐ。

エンドポイント:
- POST /api/uni-inbox/scan          : slot 全部の ac.jp/大学メールを抽出 → pending として upsert (open)
- GET  /api/uni-inbox               : 状態別一覧 (default pending)
- GET  /api/uni-inbox/counts        : pending/calendared/dismissed 件数 (バッジ用)
- POST /api/uni-inbox/{id}/calendar : その 1 件を Google Calendar に作成 → calendared
- POST /api/uni-inbox/{id}/dismiss  : 無視
- POST /api/uni-inbox/reflect-all   : pending の高信頼をまとめて反映 (1 タップ)
- POST /api/uni-inbox/remind        : 未反映 + 締切接近を Resend でメール (cron, 要 X-Cron-Token)

保管: append-only JSONL + latest-wins(id)。実 Calendar への書き込みは calendar/reflect-all の明示操作のみ。
"""

from __future__ import annotations

import re
from datetime import timedelta
from fastapi import APIRouter, HTTPException, Query, Header
from pydantic import BaseModel

from data_manager import (
    DATA_DIR, read_jsonl, append_jsonl, init_jsonl,
    generate_id, timestamp_jst, now_jst,
)

router = APIRouter()

UNI_INBOX_FILE = DATA_DIR / "uni_inbox.jsonl"
init_jsonl(UNI_INBOX_FILE, "uni_inbox", "大学メール由来の予定・締切トラッカー (pending→calendared|dismissed)")

# 処理済みメール ID。抽出は非決定的 (毎回わずかに違うタイトル/日付) なので、同じメールを
# 二度抽出すると近似重複が無限に増える。メールは一度だけ抽出する = process-once の鍵。
UNI_PROCESSED_FILE = DATA_DIR / "uni_processed_emails.jsonl"
init_jsonl(UNI_PROCESSED_FILE, "uni_processed_emails", "抽出済み Gmail メッセージ ID (再抽出防止キャッシュ)")


def _processed_ids() -> set[str]:
    return {str(e.get("email_id", "")) for e in read_jsonl(UNI_PROCESSED_FILE) if e.get("email_id")}


def _mark_processed(email_ids: list[str]) -> None:
    ts = timestamp_jst()
    for eid in email_ids:
        if eid:
            append_jsonl(UNI_PROCESSED_FILE, {"email_id": eid, "at": ts})


# ─── 状態管理 (latest-wins) ─────────────────────────────────────────────────
def _materialize() -> dict[str, dict]:
    state: dict[str, dict] = {}
    for e in read_jsonl(UNI_INBOX_FILE):
        iid = e.get("id")
        if not iid:
            continue
        if e.get("_deleted"):
            state.pop(iid, None)
            continue
        state[iid] = e
    return state


def _dedup_key(p: dict) -> str:
    """同じメールから同じ予定を再スキャンしても増えないための鍵。"""
    title = re.sub(r"\s+", "", str(p.get("title", ""))).lower()
    day = str(p.get("start_iso", ""))[:10]
    src = str(p.get("source_email_id", ""))
    return f"{src}|{title}|{day}"


def _existing_keys() -> set[str]:
    return {e.get("dedup_key", "") for e in _materialize().values()}


# ─── カレンダー二重チェック ─────────────────────────────────────────────────
def _norm(s: str) -> str:
    return re.sub(r"[\s　]+", "", str(s or "")).lower()


def _fetch_calendar_titles(days_ahead: int = 60) -> list[tuple[str, str]]:
    """(date, normalized_title) のリスト。手動で既に入れた予定との突合用。"""
    try:
        from gcal import is_configured, list_upcoming_events
        if not is_configured():
            return []
        out = []
        for ev in list_upcoming_events(days_ahead=days_ahead) or []:
            start = ev.get("start_iso", "") or ""
            out.append((start[:10], _norm(ev.get("title", ""))))
        return out
    except Exception:
        return []


# Koach OS 自身が送る通知メール (自己参照ループの元) を見分けるマーカー
_SELF_FROM_MARKERS = ("resend.dev", "koach os", "koach-os")
_SELF_SUBJECT_MARKERS = (
    "daily brief", "autopilot", "翌日スケジュール", "大学メール 未反映",
    "脳の週次", "知識の構造化",
)


def _is_self_notification(e: dict) -> bool:
    frm = str(e.get("from", "")).lower()
    if any(m in frm for m in _SELF_FROM_MARKERS):
        return True
    subj = str(e.get("subject", "")).lower()
    return any(m in subj for m in _SELF_SUBJECT_MARKERS)


def _already_in_calendar(p: dict, cal: list[tuple[str, str]]) -> bool:
    """同じ日付で、タイトルが一方に含まれていれば「既にある」とみなす (ゆるめ)。"""
    day = str(p.get("start_iso", ""))[:10]
    if not day:
        return False
    t = _norm(p.get("title", ""))
    if len(t) < 3:
        return False
    for cday, ctitle in cal:
        if cday != day or not ctitle:
            continue
        if t in ctitle or ctitle in t:
            return True
    return False


# ─── スキャン (抽出 → upsert) ───────────────────────────────────────────────
class ScanReq(BaseModel):
    days: int = 7          # 何日ぶんのメールを見るか
    max_per_slot: int = 50
    engine: str = "gemini"


# 「確実に大学から来ているもの」= 送信元が ac.jp のメールだけ。キーワード一致 (委員会/講義…)
# は販促・ニュースまで拾ってノイズと抽出揺れの元になるので使わない。送信元限定で精度を上げる。
UNI_SENDER_QUERY = "(from:ac.jp OR from:hokudai.ac.jp)"


def _scan(days: int, max_per_slot: int, engine: str) -> dict:
    from gcal import is_configured, list_recent_emails, _configured_slots
    from routers.gmail_calendar import _build_system_prompt, _process_batch, BATCH_SIZE
    from data_manager import now_jst as _now
    from router import DEFAULT_MODELS

    if not is_configured():
        raise HTTPException(400, "Google integration not configured")

    # 送信元が大学 (ac.jp) のメールだけを各アカウントから取得
    emails: list[dict] = []
    seen_ids: set[str] = set()
    errors: list[str] = []
    self_skipped = 0
    for slot in _configured_slots():
        try:
            got = list_recent_emails(
                days=days, max_results=max_per_slot, slot=slot,
                query_extra=UNI_SENDER_QUERY,
            )
            for e in got:
                eid = e.get("id", "")
                if eid and eid in seen_ids:
                    continue
                if eid:
                    seen_ids.add(eid)
                # Koach OS 自身の通知メール (Daily Brief / Autopilot 等) を除外。
                # キーワード一致で自分の生成物を「大学予定」として再取り込みするのを防ぐ。
                if _is_self_notification(e):
                    self_skipped += 1
                    continue
                emails.append(e)
        except Exception as ex:
            errors.append(f"slot {slot}: {ex}")

    # process-once: 既に抽出したメールは二度と抽出しない (近似重複の無限増殖を防ぐ)
    processed = _processed_ids()
    fresh = [e for e in emails if e.get("id", "") not in processed]

    if not fresh:
        return {"emails_scanned": len(emails), "fresh_emails": 0, "self_skipped": self_skipped,
                "extracted": 0, "new_pending": 0, "already_calendar": 0, "duplicate": 0,
                "errors": errors, "note": "新規メールなし (全て抽出済み)"}

    today_str = _now().strftime("%Y-%m-%d (%A)")
    system_prompt = _build_system_prompt(today_str)
    eng = engine if engine in DEFAULT_MODELS else "gemini"
    model = DEFAULT_MODELS.get(eng, DEFAULT_MODELS["gemini"])

    proposals: list[dict] = []
    processed_ok: list[str] = []
    ai_failures = 0
    for i in range(0, len(fresh), BATCH_SIZE):
        batch = fresh[i:i + BATCH_SIZE]
        props, err, _preview = _process_batch(batch, system_prompt, eng, model)
        proposals.extend(props)
        # AI 呼び出し自体が失敗したバッチは処理済みにしない → 次回リトライ (取りこぼし防止)。
        # JSON パース失敗 (recovered_partial 等) は抽出は走ったので処理済みにする。
        if err and str(err).startswith("AI call failed"):
            ai_failures += 1
            continue
        processed_ok.extend(e.get("id", "") for e in batch)

    # 抽出が成功したメールだけ処理済みに (イベント0件でもOK)
    _mark_processed(processed_ok)

    # 送信元を引けるように email_id → from を持っておく
    from_by_id = {e.get("id", ""): e.get("from", "") for e in fresh}

    cal = _fetch_calendar_titles(days_ahead=90)
    existing = _existing_keys()

    new_pending = already_cal = duplicate = 0
    for idx, p in enumerate(proposals):
        if not p.get("title") or not p.get("start_iso"):
            continue
        key = _dedup_key(p)
        if key in existing:
            duplicate += 1
            continue
        existing.add(key)

        in_cal = _already_in_calendar(p, cal)
        # generate_id は秒解像度で、同一スキャン内の連続 append が衝突する。
        # マイクロ秒 + index で一意化 (latest-wins で潰れないように)。
        uid = f"uni_{now_jst().strftime('%Y%m%d_%H%M%S_%f')}_{idx}"
        item = {
            "id": uid,
            "dedup_key": key,
            "title": str(p.get("title", ""))[:200],
            "start_iso": str(p.get("start_iso", "")),
            "end_iso": str(p.get("end_iso", "")),
            "description": str(p.get("description", ""))[:500],
            "location": str(p.get("location", ""))[:200],
            "confidence": p.get("confidence", "medium"),
            "event_type": p.get("event_type", "default"),
            "source_email_id": str(p.get("source_email_id", "")),
            "source_subject": str(p.get("source_subject", ""))[:200],
            "source_from": str(from_by_id.get(str(p.get("source_email_id", "")), ""))[:120],
            "status": "calendared" if in_cal else "pending",
            "calendar_event_id": "external" if in_cal else "",
            "created_at": timestamp_jst(),
            "updated_at": timestamp_jst(),
        }
        append_jsonl(UNI_INBOX_FILE, item)
        if in_cal:
            already_cal += 1
        else:
            new_pending += 1

    # 抽出は非決定的なので、万一 pending に近似重複が残っても末尾で畳む (自己浄化)
    collapsed = _collapse_near_dups()

    return {
        "emails_scanned": len(emails),
        "fresh_emails": len(fresh),
        "self_skipped": self_skipped,
        "extracted": len(proposals),
        "new_pending": new_pending,
        "already_calendar": already_cal,
        "duplicate": duplicate,
        "deduped": collapsed,
        "ai_failures": ai_failures,
        "engine_used": eng,
        "errors": errors,
    }


def _collapse_near_dups() -> int:
    """pending のうち (日付, タイトル先頭) が同じ近似重複を畳む。信頼度が高い1件を残し他は dismiss。
    抽出の揺れ (『(木村美玖)』vs『（木村美玖さん）』等) で増えた重複を掃除する。可逆 (dismissed に退避)。"""
    pend = [e for e in _materialize().values() if e.get("status") == "pending"]
    groups: dict[tuple, list] = {}
    for it in pend:
        day = str(it.get("start_iso", ""))[:10]
        prefix = _norm(it.get("title", ""))[:16]
        if not day or not prefix:
            continue
        groups.setdefault((day, prefix), []).append(it)

    conf_rank = {"high": 2, "medium": 1, "low": 0}
    collapsed = 0
    for group in groups.values():
        if len(group) < 2:
            continue
        # 残す1件: 信頼度 高 > 時刻あり > 早く登録された順
        group.sort(key=lambda it: (
            conf_rank.get(it.get("confidence", "medium"), 1),
            1 if "T" in str(it.get("start_iso", "")) else 0,
            it.get("created_at", ""),
        ), reverse=True)
        for it in group[1:]:
            append_jsonl(UNI_INBOX_FILE, {**it, "status": "dismissed",
                                          "dismiss_reason": "near-duplicate",
                                          "updated_at": timestamp_jst()})
            collapsed += 1
    return collapsed


@router.post("/uni-inbox/scan")
def scan(req: ScanReq):
    """大学メールを抽出して未反映として登録。UI の『今すぐスキャン』と cron の両方から呼べる。"""
    return _scan(req.days, req.max_per_slot, req.engine)


@router.post("/uni-inbox/dedupe")
def dedupe():
    """pending の近似重複を畳む (手動)。散らかった状態の掃除に使う。token 不要 (dismiss と同格の可逆操作)。"""
    n = _collapse_near_dups()
    return {"ok": True, "deduped": n}


# ─── 一覧 / 件数 ────────────────────────────────────────────────────────────
@router.get("/uni-inbox")
def list_items(status: str = Query("pending", description="pending|calendared|dismissed|(空で全部)")):
    items = list(_materialize().values())
    if status:
        items = [e for e in items if e.get("status") == status]
    # 締切・日付が近い順
    items.sort(key=lambda x: x.get("start_iso", "") or "9999")
    return {"items": items, "count": len(items)}


@router.get("/uni-inbox/counts")
def counts():
    out = {"pending": 0, "calendared": 0, "dismissed": 0}
    for e in _materialize().values():
        s = e.get("status", "")
        if s in out:
            out[s] += 1
    return out


def _wipe(reset_processed: bool = True) -> int:
    """全トラッカー項目を tombstone で無効化 + 処理済みキャッシュを truncate。返り値=消した件数。
    実 Calendar には触れない (作成済みイベントは Google Calendar 側に残る)。"""
    live = _materialize()
    for iid in list(live.keys()):
        append_jsonl(UNI_INBOX_FILE, {"id": iid, "_deleted": True, "at": timestamp_jst()})
    if reset_processed:
        import json as _json
        with open(UNI_PROCESSED_FILE, "w", encoding="utf-8") as f:
            f.write(_json.dumps({"_schema": "uni_processed_emails", "_version": "2.0",
                                 "_description": "抽出済み Gmail メッセージ ID (再抽出防止キャッシュ)"},
                                ensure_ascii=False) + "\n")
    return len(live)


@router.post("/uni-inbox/purge")
def purge(
    reset_processed: bool = Query(True, description="処理済みメールキャッシュも消して再取り込み可能にするか"),
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    """メンテナンス用 (cron/token): 全トラッカー項目を tombstone で無効化。"""
    _check_token(x_cron_token)
    n = _wipe(reset_processed)
    return {"ok": True, "tombstoned": n, "processed_reset": reset_processed}


class RebuildReq(BaseModel):
    days: int = 14
    max_per_slot: int = 50


@router.post("/uni-inbox/rebuild")
def rebuild(req: RebuildReq):
    """UI の『リセットして取り込み直す』用: 全消し → 大学メールを新規スキャン。
    token 不要 (本人が UI から明示操作する scan/dismiss と同格)。実 Calendar には触れない。"""
    tombstoned = _wipe(reset_processed=True)
    result = _scan(req.days, req.max_per_slot, "gemini")
    result["tombstoned"] = tombstoned
    return result


# ─── 反映 / 無視 ────────────────────────────────────────────────────────────
def _create_calendar_event(item: dict) -> str:
    from gcal import is_configured, create_event
    if not is_configured():
        raise HTTPException(400, "Google Calendar not configured")
    result = create_event(
        title=item.get("title", "(無題)"),
        start_iso=item.get("start_iso", ""),
        end_iso=item.get("end_iso", "") or item.get("start_iso", ""),
        description=(item.get("description", "") + f"\n\n[大学メール] {item.get('source_subject','')}").strip(),
        location=item.get("location", ""),
        event_type=item.get("event_type", "default"),
    )
    return result.get("id", "")


@router.post("/uni-inbox/{iid}/calendar")
def to_calendar(iid: str):
    st = _materialize()
    item = st.get(iid)
    if not item:
        raise HTTPException(404, "item not found")
    if item.get("status") == "calendared":
        return {"ok": True, "already": True, "calendar_event_id": item.get("calendar_event_id")}
    try:
        ev_id = _create_calendar_event(item)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"calendar create failed: {e}")
    updated = {**item, "status": "calendared", "calendar_event_id": ev_id,
               "updated_at": timestamp_jst()}
    append_jsonl(UNI_INBOX_FILE, updated)
    return {"ok": True, "calendar_event_id": ev_id}


@router.post("/uni-inbox/{iid}/dismiss")
def dismiss(iid: str):
    st = _materialize()
    item = st.get(iid)
    if not item:
        raise HTTPException(404, "item not found")
    updated = {**item, "status": "dismissed", "updated_at": timestamp_jst()}
    append_jsonl(UNI_INBOX_FILE, updated)
    return {"ok": True}


class ReflectAllReq(BaseModel):
    min_confidence: str = "high"   # high のみ / medium で medium+high


@router.post("/uni-inbox/reflect-all")
def reflect_all(req: ReflectAllReq):
    """未反映のうち信頼度が閾値以上のものをまとめてカレンダーへ (1 タップ反映)。"""
    order = {"low": 0, "medium": 1, "high": 2}
    threshold = order.get(req.min_confidence, 2)
    reflected, errors, skipped = [], [], 0
    for item in sorted(_materialize().values(), key=lambda x: x.get("start_iso", "")):
        if item.get("status") != "pending":
            continue
        if order.get(item.get("confidence", "medium"), 1) < threshold:
            skipped += 1
            continue
        try:
            ev_id = _create_calendar_event(item)
            append_jsonl(UNI_INBOX_FILE, {**item, "status": "calendared",
                                          "calendar_event_id": ev_id, "updated_at": timestamp_jst()})
            reflected.append({"title": item.get("title"), "start": item.get("start_iso")})
        except Exception as e:
            errors.append(f"{item.get('title','')}: {e}")
    return {"ok": not errors, "reflected": len(reflected), "items": reflected,
            "skipped_low_confidence": skipped, "errors": errors}


# ─── リマインド (忘れていませんか) ──────────────────────────────────────────
from routers.cron import _check_token


def _remind_text(pending: list[dict]) -> tuple[str, int]:
    now = now_jst()
    soon_cut = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    today = now.strftime("%Y-%m-%d")

    soon, later = [], []
    for it in pending:
        day = str(it.get("start_iso", ""))[:10]
        (soon if day and today <= day <= soon_cut else later).append(it)
    soon.sort(key=lambda x: x.get("start_iso", ""))
    later.sort(key=lambda x: x.get("start_iso", ""))

    def _line(it: dict) -> str:
        day = str(it.get("start_iso", ""))[:10] or "日付未定"
        tm = ""
        s = it.get("start_iso", "")
        if "T" in s:
            tm = " " + s[11:16]
        tag = {"deadline": "〆", "committee": "委", "meeting": "会"}.get(it.get("event_type", ""), "・")
        return f"  [{tag}] {day}{tm}  {str(it.get('title',''))[:70]}"

    lines = [f"大学メールの未反映 {len(pending)} 件 — 忘れていませんか？", ""]
    if soon:
        lines.append(f"■ 今週まで ({len(soon)} 件) — 先にカレンダーへ")
        lines += [_line(it) for it in soon]
        lines.append("")
    if later:
        lines.append(f"■ その先 / 日付未定 ({len(later)} 件)")
        lines += [_line(it) for it in later[:15]]
        lines.append("")
    lines.append("反映は Koach OS の『🎓 大学メール』(/uni-inbox) から 1 タップでできます。")
    return "\n".join(lines), len(soon)


@router.post("/uni-inbox/remind")
def remind(
    auto_scan: bool = Query(True, description="リマインド前に最新メールをスキャンするか"),
    days: int = Query(7),
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    """cron 用: 先にスキャンして未反映を最新化 → 未反映があれば Resend でメール。"""
    _check_token(x_cron_token)

    scan_result = None
    if auto_scan:
        try:
            scan_result = _scan(days=days, max_per_slot=50, engine="gemini")
        except Exception as e:
            scan_result = {"error": str(e)}

    pending = [e for e in _materialize().values() if e.get("status") == "pending"]
    if not pending:
        return {"ok": True, "pending": 0, "emailed": False, "scan": scan_result,
                "note": "未反映なし。リマインド送信せず。"}

    text, soon_n = _remind_text(pending)
    from routers.autopilot import _send_report_email
    subject = f"🎓 大学メール 未反映 {len(pending)}件" + (f" (今週まで{soon_n})" if soon_n else "")
    emailed = _send_report_email(subject, text)
    return {"ok": True, "pending": len(pending), "soon": soon_n,
            "emailed": emailed, "scan": scan_result}
