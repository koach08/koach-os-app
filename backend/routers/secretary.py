"""
秘書 (Secretary) — 突発予定 / 予定外の仕事を入れたら、既存予定を自動で組み直す。

設計方針 (ユーザー確定):
- 反映方式: **提案 → 確認 → 適用** (実カレンダーを勝手に動かさない)
- 可動範囲: **締切以外すべて**。ただし家族 / 健康 / 保育園 (life_blocks 系) は
  「動かすコスト高」として最後の手段にし、提案時に警告フラグを立てる。

エンドポイント:
POST /api/secretary/intake     — 自由文を解析 → 衝突検出 → 組み直し案 (書き込まない)
POST /api/secretary/apply      — 確認後に新予定作成 + 既存予定/タスク移動を実行
POST /api/secretary/from-email — kshgks59 (slot 2) のメールを読んでタスク/予定化 + 配置案
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from data_manager import now_jst
from router import call_ai, DEFAULT_MODELS

router = APIRouter()

JST = timezone(timedelta(hours=9))


# ─── JSON 救出パース ───────────────────────────────────────────────────────
def _parse_json(raw: str):
    cleaned = (raw or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        # 最初の { …最後の } / 最初の [ …最後の ]
        for pat in (r"\{.*\}", r"\[.*\]"):
            m = re.search(pat, cleaned, re.DOTALL)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception:
                    continue
        return None


def _engine_model(engine: str) -> tuple[str, str]:
    if engine not in DEFAULT_MODELS:
        engine = "gpt"
    return engine, DEFAULT_MODELS[engine]


def _iso(date_str: str, hm: str) -> str:
    """YYYY-MM-DD + HH:MM → JST ISO."""
    dt = datetime.fromisoformat(f"{date_str}T{hm}:00").replace(tzinfo=JST)
    return dt.isoformat()


def _to_local(iso: str) -> datetime | None:
    if not iso or "T" not in iso:
        return None
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST)
    except Exception:
        return None


# 家族 / 健康 / 保育園 を示すキーワード (= 動かすコスト高)
_PROTECTED_KW = [
    "家族", "妻", "子ども", "子供", "保育園", "幼稚園", "送迎", "お迎え", "送り",
    "夕食", "就寝", "寝かしつけ", "病院", "通院", "family", "training",
    "トレーニング", "運動", "ジム", "ブレイキン", "休息", "散歩",
]


def _is_protected(title: str, category: str = "") -> bool:
    text = f"{title} {category}".lower()
    return any(kw.lower() in text for kw in _PROTECTED_KW)


# ─── カレンダー / タスク取得 ───────────────────────────────────────────────
def _fetch_events(start_date: str, end_date: str) -> list[dict]:
    try:
        from gcal import is_configured, list_events_range_multi
    except Exception:
        return []
    if not is_configured():
        return []
    try:
        return list_events_range_multi(start_date=start_date, end_date=end_date)
    except Exception:
        return []


def _scheduled_tasks() -> list[dict]:
    """due_time を持つ (= 時刻が決まっている) 未完了タスク。移動候補。"""
    try:
        from routers.tasks import _materialize_state
        out = []
        for t in _materialize_state().values():
            if t.get("status") == "done":
                continue
            if t.get("due_date") and t.get("due_time"):
                out.append(t)
        return out
    except Exception:
        return []


def _free_slots(days_ahead: int, min_minutes: int) -> list[dict]:
    try:
        from routers.scheduling import _find_free_slots
        return _find_free_slots(days_ahead=days_ahead, min_minutes=min_minutes)
    except Exception:
        return []


def _overlaps(s1: datetime, e1: datetime, s2: datetime, e2: datetime) -> bool:
    return s1 < e2 and s2 < e1


# ─── 1. 自由文 → 構造化 ────────────────────────────────────────────────────
PARSE_SYSTEM = """あなたは志柿浩一郎 (北海道大学 准教授) の秘書。
入力された自由文を「突発の予定」か「予定外の仕事 (タスク)」として構造化する。

判定:
- kind="fixed_event": 開始時刻が決まっている来客・会議・面談・送迎など (動かせない予定として新規に入る)
- kind="task": 締切までに終わらせる作業 (執筆・採点・資料作成など。空き時間に割り当てる)

出力 JSON (これのみ。Markdown 禁止):
{
  "kind": "fixed_event" | "task",
  "title": "簡潔なタイトル",
  "date": "YYYY-MM-DD" | null,        // fixed_event は必須。相対表現は今日基準で解決
  "start_time": "HH:MM" | null,        // fixed_event で時刻があれば
  "end_time": "HH:MM" | null,
  "all_day": false,
  "estimated_minutes": 60,             // task の所要 / fixed_event で終了未指定時の幅
  "deadline_date": "YYYY-MM-DD" | null,// task の締切
  "category": "class|deadline|research|growth|training|family|personal",
  "event_type": "meeting|committee|deadline|default",
  "location": "",
  "interpretation": "どう解釈したか 1 行"
}

ルール:
- 「明日」「来週月曜」「金曜まで」などの相対表現は与えられた現在日時で絶対日付に変換
- 会議/面談/来客 → category=class, event_type=meeting
- 提出/締切/レポート → category=deadline, event_type=deadline
- 時刻が全く読めない fixed_event は all_day=true"""


def _parse_input(text: str, engine: str) -> dict:
    eng, model = _engine_model(engine)
    user = f"現在: {now_jst().strftime('%Y-%m-%d %H:%M (%A)')}\n\n入力:\n{text}"
    try:
        raw = call_ai(
            messages=[{"role": "user", "content": user}],
            system=PARSE_SYSTEM,
            engine=eng,
            model=model,
            max_tokens=600,
        )
    except Exception as e:
        raise HTTPException(500, f"parse failed: {e}")
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict) or not parsed.get("title"):
        raise HTTPException(422, f"入力を解析できませんでした: {raw[:200]}")
    return parsed


# ─── 2. 組み直し案を AI に作らせる ─────────────────────────────────────────
PLAN_SYSTEM = """あなたは志柿の秘書。新しく入った予定 / 仕事のために、既存の「動かせる予定」を
空き時間へ組み直す案を作る。

優先順位 (動かす順 = 守る順の逆): 家族 > 学生 > 研究 > プラットフォーム > 収益 > 個人成長
- 締切 (deadline) は絶対に動かさない (入力に含まれない)
- protected=true (家族/健康/保育園/トレーニング) は最後の手段。動かすなら protected_move=true を立て理由を書く
- 動かせる仕事ブロックを先に動かして衝突を解消する
- 各移動先は提示された「利用可能な時間帯」から選ぶ。被らないように
- 1 つも動かす必要がなければ moves は空配列

出力 JSON (これのみ):
{
  "moves": [
    {"ref_kind":"event"|"task","ref_id":"...","title":"...",
     "new_start_iso":"YYYY-MM-DDTHH:MM:SS+09:00","new_end_iso":"...",
     "reason":"なぜここへ","protected_move":false}
  ],
  "place_new": {"start_iso":"...","end_iso":"..."} | null,
  "unplaceable": [{"title":"...","why":"空きが足りない 等"}],
  "balance_note": "家族・健康への影響を 1 行 (なければ '影響なし')",
  "summary": "1〜2 文。です/ます調、抽象名詞『〜性』NG、煽らない"
}

place_new は kind=task のときだけ「新しい仕事をどこに置くか」を埋める。fixed_event のときは null。"""


def _build_plan(new_item: dict, movable: list[dict], availability_text: str,
                kind: str, engine: str) -> dict:
    eng, model = _engine_model(engine)

    movable_text = "\n".join(
        f"- [{m['ref_kind']}:{m['ref_id']}] {m['title']} "
        f"現在 {m['cur_start'][11:16]}〜{m['cur_end'][11:16]} "
        f"(category={m.get('category','?')}{', protected' if m.get('protected') else ''})"
        for m in movable
    ) or "(衝突する動かせる予定なし)"

    if kind == "fixed_event":
        ni = (f"{new_item['title']} を {new_item['start_iso'][:16].replace('T',' ')}"
              f"〜{new_item['end_iso'][11:16]} に固定で入れる")
    else:
        ni = (f"仕事「{new_item['title']}」(約 {new_item.get('estimated_minutes',60)}分"
              + (f", 締切 {new_item['deadline_date']}" if new_item.get('deadline_date') else "")
              + ") を空き時間に割り当てる")

    user = f"""現在: {now_jst().strftime('%Y-%m-%d %H:%M (%A)')}

## 新しく入るもの
{ni}

## 衝突して動かす必要がある既存の予定 / タスク
{movable_text}

## 利用可能な時間帯 (ここから移動先を選ぶ)
{availability_text}

組み直し案を JSON で出してください。"""

    try:
        raw = call_ai(
            messages=[{"role": "user", "content": user}],
            system=PLAN_SYSTEM,
            engine=eng,
            model=model,
            max_tokens=1800,
        )
    except Exception as e:
        raise HTTPException(500, f"plan failed: {e}")
    plan = _parse_json(raw)
    if not isinstance(plan, dict):
        plan = {"moves": [], "place_new": None, "unplaceable": [],
                "balance_note": "", "summary": "(案を生成できませんでした)"}
    plan.setdefault("moves", [])
    plan.setdefault("unplaceable", [])
    plan.setdefault("place_new", None)
    plan.setdefault("balance_note", "")
    plan.setdefault("summary", "")
    return plan


# ─── intake ────────────────────────────────────────────────────────────────
class IntakeReq(BaseModel):
    text: str
    days_ahead: int = 5
    engine: str = "gpt"


@router.post("/secretary/intake")
def intake(req: IntakeReq):
    if not req.text.strip():
        raise HTTPException(400, "text が空です")

    parsed = _parse_input(req.text, req.engine)
    kind = parsed.get("kind", "task")
    days = max(1, min(req.days_ahead, 21))

    # 新アイテムの時刻を確定
    new_item: dict = {
        "kind": kind,
        "title": parsed.get("title", "(無題)"),
        "category": parsed.get("category", "personal"),
        "event_type": parsed.get("event_type", "default"),
        "location": parsed.get("location", ""),
        "all_day": bool(parsed.get("all_day")),
        "estimated_minutes": int(parsed.get("estimated_minutes") or 60),
        "deadline_date": parsed.get("deadline_date"),
        "interpretation": parsed.get("interpretation", ""),
    }

    movable: list[dict] = []
    new_start = new_end = None

    if kind == "fixed_event":
        date = parsed.get("date")
        if not date:
            raise HTTPException(422, "突発予定の日付を読み取れませんでした")
        if new_item["all_day"] or not parsed.get("start_time"):
            new_item.update({"start_iso": date, "end_iso": date, "all_day": True})
        else:
            st = parsed["start_time"]
            new_start = _to_local(_iso(date, st))
            if parsed.get("end_time"):
                new_end = _to_local(_iso(date, parsed["end_time"]))
            if not new_end or new_end <= new_start:
                new_end = new_start + timedelta(minutes=new_item["estimated_minutes"])
            new_item["start_iso"] = new_start.isoformat()
            new_item["end_iso"] = new_end.isoformat()

        # 衝突検出 (時刻ありのときのみ)
        if new_start and new_end:
            day = new_start.strftime("%Y-%m-%d")
            day_next = (new_start + timedelta(days=1)).strftime("%Y-%m-%d")
            for ev in _fetch_events(day, day_next):
                if ev.get("all_day"):
                    continue
                s = _to_local(ev.get("start_iso", ""))
                e_ = _to_local(ev.get("end_iso", ""))
                if not s or not e_ or not _overlaps(new_start, new_end, s, e_):
                    continue
                # 締切は動かさない
                if ev.get("event_type") == "deadline":
                    continue
                movable.append({
                    "ref_kind": "event",
                    "ref_id": ev.get("id", ""),
                    "calendar_id": ev.get("calendar_id", "primary"),
                    "slot": ev.get("slot", 1),
                    "gcal_event_id": ev.get("id", ""),
                    "title": ev.get("title", "(無題)"),
                    "cur_start": ev.get("start_iso", ""),
                    "cur_end": ev.get("end_iso", ""),
                    "category": ev.get("event_type", ""),
                    "protected": _is_protected(ev.get("title", ""), ev.get("event_type", "")),
                })
            # 衝突するスケジュール済みタスク
            for t in _scheduled_tasks():
                ts = _to_local(_iso(t["due_date"], t["due_time"]))
                if not ts:
                    continue
                te = ts + timedelta(minutes=int(t.get("estimated_minutes") or 60))
                if not _overlaps(new_start, new_end, ts, te):
                    continue
                movable.append({
                    "ref_kind": "task",
                    "ref_id": t["id"],
                    "gcal_event_id": t.get("gcal_event_id"),
                    "title": t.get("title", "(無題)"),
                    "cur_start": ts.isoformat(),
                    "cur_end": te.isoformat(),
                    "category": t.get("category", ""),
                    "protected": _is_protected(t.get("title", ""), t.get("category", "")),
                })

    # 利用可能な時間帯 = 空きスロット (新予定の時間は除外) + 退避する予定の元枠
    raw_slots = _free_slots(days_ahead=days, min_minutes=30)
    avail_lines: list[str] = []
    for s in raw_slots:
        ss = _to_local(s["start_iso"])
        se = _to_local(s["end_iso"])
        if not ss or not se:
            continue
        # 新しい固定予定と被る空きは除外
        if new_start and new_end and _overlaps(ss, se, new_start, new_end):
            continue
        avail_lines.append(f"- {s['date']} {s['start_iso'][11:16]}〜{s['end_iso'][11:16]} ({s['minutes']}分)")
    for m in movable:
        avail_lines.append(f"- (空く) {m['cur_start'][:10]} {m['cur_start'][11:16]}〜{m['cur_end'][11:16]}")
    availability_text = "\n".join(avail_lines) or "(空きなし)"

    plan = _build_plan(new_item, movable, availability_text, kind, req.engine)

    # 移動指示に実行用メタ (calendar_id/slot) を補完
    meta_by_id = {m["ref_id"]: m for m in movable}
    for mv in plan.get("moves", []):
        src = meta_by_id.get(mv.get("ref_id"))
        if src:
            mv["calendar_id"] = src.get("calendar_id", "primary")
            mv["slot"] = src.get("slot", 1)
            mv["gcal_event_id"] = src.get("gcal_event_id")
            mv["cur_start"] = src.get("cur_start")
            mv["cur_end"] = src.get("cur_end")
            mv["protected"] = src.get("protected", False)

    # task の場合は place_new を新アイテムの時刻に反映
    if kind == "task" and plan.get("place_new"):
        new_item["start_iso"] = plan["place_new"].get("start_iso")
        new_item["end_iso"] = plan["place_new"].get("end_iso")
        new_item["all_day"] = False

    has_protected = any(m.get("protected") for m in plan.get("moves", []))

    return {
        "generated_at": now_jst().isoformat(),
        "new_item": new_item,
        "conflicts_found": len(movable),
        "plan": plan,
        "has_protected_move": has_protected,
    }


# ─── apply ───────────────────────────────────────────────────────────────────
class MoveOp(BaseModel):
    ref_kind: str               # event | task
    ref_id: str
    title: str = ""
    new_start_iso: str
    new_end_iso: str
    calendar_id: str = "primary"
    slot: int = 1
    gcal_event_id: str | None = None


class NewItem(BaseModel):
    kind: str = "fixed_event"
    title: str
    start_iso: str = ""
    end_iso: str = ""
    all_day: bool = False
    category: str = "personal"
    event_type: str = "default"
    location: str = ""
    create: bool = True         # false なら新規作成しない (案だけ確認したいとき)


class ApplyReq(BaseModel):
    new_item: NewItem | None = None
    moves: list[MoveOp] = []


@router.post("/secretary/apply")
def apply(req: ApplyReq):
    from gcal import is_configured, create_event, update_event
    if not is_configured():
        raise HTTPException(400, "Google Calendar not configured")

    results: dict = {"created": None, "moved": [], "errors": []}

    # 1) 新アイテムを作成
    if req.new_item and req.new_item.create and req.new_item.start_iso:
        ni = req.new_item
        try:
            ev = create_event(
                title=ni.title,
                start_iso=ni.start_iso,
                end_iso=ni.end_iso,
                description="",
                location=ni.location,
                event_type=ni.event_type,
            )
            results["created"] = {"title": ni.title, "event_id": ev.get("id"),
                                  "html_link": ev.get("htmlLink")}
        except Exception as e:
            results["errors"].append(f"新予定作成失敗: {e}")

    # 2) 既存予定 / タスクを移動
    for mv in req.moves:
        try:
            if mv.ref_kind == "event":
                update_event(
                    mv.gcal_event_id or mv.ref_id,
                    calendar_id=mv.calendar_id or "primary",
                    slot=mv.slot or 1,
                    start_iso=mv.new_start_iso,
                    end_iso=mv.new_end_iso,
                )
                results["moved"].append({"title": mv.title, "kind": "event", "ok": True})
            else:  # task
                _move_task(mv, update_event)
                results["moved"].append({"title": mv.title, "kind": "task", "ok": True})
        except Exception as e:
            results["errors"].append(f"移動失敗 {mv.title}: {e}")

    results["ok"] = not results["errors"]
    return results


def _move_task(mv: MoveOp, update_event) -> None:
    """タスクの due_date/due_time を更新し、Calendar に紐づくならイベントも動かす。"""
    from routers.tasks import _get, _save
    from data_manager import timestamp_jst
    task = _get(mv.ref_id)
    if not task:
        raise RuntimeError("task not found")
    s = _to_local(mv.new_start_iso)
    if not s:
        raise RuntimeError("bad new_start_iso")
    new = {
        **task,
        "due_date": s.strftime("%Y-%m-%d"),
        "due_time": s.strftime("%H:%M"),
        "updated_at": timestamp_jst(),
    }
    _save(new)
    if task.get("gcal_event_id"):
        update_event(
            task["gcal_event_id"],
            calendar_id="primary",
            slot=1,
            start_iso=mv.new_start_iso,
            end_iso=mv.new_end_iso,
        )


# ─── from-email (kshgks59 → タスク/予定化 + 配置案) ──────────────────────────
EMAIL_EXTRACT_SYSTEM = """あなたは志柿の秘書。受信メール群から「行動が必要な仕事 / 予定」を抽出する。

各メールについて、対応が必要なら 1 件以上のアクションを出す。情報のみ・広告・自動通知は無視。

出力 JSON (これのみ):
{
  "items": [
    {
      "kind": "fixed_event" | "task",
      "title": "何をするか (動詞で)",
      "date": "YYYY-MM-DD" | null,
      "start_time": "HH:MM" | null,
      "estimated_minutes": 30,
      "deadline_date": "YYYY-MM-DD" | null,
      "category": "class|deadline|research|growth|family|personal",
      "source_subject": "元メール件名",
      "reason": "なぜ対応が必要か 1 行"
    }
  ]
}

ルール:
- 会議/面談の日時が指定 → kind=fixed_event
- 提出/返信/作業 → kind=task。締切が本文にあれば deadline_date
- 締切も日時もないが対応必要 → kind=task, deadline_date=null
- 相対日付は現在日時基準で絶対化
- です/ます調、抽象名詞『〜性』NG"""


class FromEmailReq(BaseModel):
    slot: int = 2          # kshgks59
    days: int = 7
    max_emails: int = 30
    days_ahead: int = 7
    engine: str = "gpt"


@router.post("/secretary/from-email")
def from_email(req: FromEmailReq):
    from gcal import is_configured, list_recent_emails
    if not is_configured():
        raise HTTPException(400, "Google integration not configured")

    try:
        emails = list_recent_emails(days=req.days, max_results=req.max_emails, slot=req.slot)
    except Exception as e:
        raise HTTPException(500, f"Gmail fetch failed: {e}")

    if not emails:
        return {"items": [], "count": 0, "summary": "対象メールなし"}

    batch = "\n\n".join(
        f"---\nFrom: {e.get('from','')}\nSubject: {e.get('subject','')}\n"
        f"Snippet: {e.get('snippet','')[:300]}\nBody: {e.get('body','')[:600]}"
        for e in emails
    )
    eng, model = _engine_model(req.engine)
    user = f"現在: {now_jst().strftime('%Y-%m-%d %H:%M (%A)')}\n\n以下 {len(emails)} 件のメール:\n\n{batch}"
    try:
        raw = call_ai(
            messages=[{"role": "user", "content": user}],
            system=EMAIL_EXTRACT_SYSTEM,
            engine=eng,
            model=model,
            max_tokens=2500,
        )
    except Exception as e:
        raise HTTPException(500, f"AI extract failed: {e}")
    parsed = _parse_json(raw) or {}
    items = parsed.get("items", []) if isinstance(parsed, dict) else []

    # 各アイテムを空きに配置 (task) / 時刻確定 (fixed_event)
    raw_slots = _free_slots(days_ahead=max(1, min(req.days_ahead, 21)), min_minutes=30)
    slot_lines = "\n".join(
        f"- {s['date']} {s['start_iso'][11:16]}〜{s['end_iso'][11:16]} ({s['minutes']}分)"
        for s in raw_slots
    ) or "(空きなし)"

    enriched = []
    for it in items[:25]:
        kind = it.get("kind", "task")
        entry = {
            "kind": kind,
            "title": it.get("title", "(無題)"),
            "category": it.get("category", "personal"),
            "estimated_minutes": int(it.get("estimated_minutes") or 30),
            "deadline_date": it.get("deadline_date"),
            "source_subject": it.get("source_subject", ""),
            "reason": it.get("reason", ""),
            "suggested_start_iso": None,
            "suggested_end_iso": None,
        }
        if kind == "fixed_event" and it.get("date") and it.get("start_time"):
            ss = _to_local(_iso(it["date"], it["start_time"]))
            if ss:
                entry["suggested_start_iso"] = ss.isoformat()
                entry["suggested_end_iso"] = (ss + timedelta(minutes=entry["estimated_minutes"])).isoformat()
        enriched.append(entry)

    return {
        "items": enriched,
        "count": len(enriched),
        "free_slots_text": slot_lines,
        "emails_scanned": len(emails),
        "note": "task は適用時に『秘書タブ』へ流し込んで空きへ配置できます。fixed_event は候補時刻を確認のうえ予定追加してください。",
    }
