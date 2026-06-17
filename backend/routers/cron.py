"""
Cron endpoints — external scheduled triggers (GitHub Actions etc.)

- POST /api/cron/notify-brief   : Daily Brief を生成して Resend で Gmail に送信
- POST /api/cron/snapshot-data  : data/ 配下を tar.gz → base64 で return

Auth: header `X-Cron-Token` が env CRON_TOKEN と一致しないと 401。

Resend env:
- RESEND_API_KEY : https://resend.com/ で取得 (re_ から始まる文字列)
- NOTIFY_EMAIL   : 送信先 (例: japanesebusinessman4@gmail.com)
- NOTIFY_FROM    : 送信元 (省略時は `Koach OS <onboarding@resend.dev>`)
"""

import os
import io
import json
import base64
import tarfile
import urllib.request
import urllib.error
from datetime import datetime

from fastapi import APIRouter, Header, HTTPException

from data_manager import DATA_DIR

router = APIRouter()


def _check_token(token: str | None) -> None:
    expected = os.environ.get("CRON_TOKEN", "")
    if not expected:
        raise HTTPException(503, "CRON_TOKEN not configured")
    if token != expected:
        raise HTTPException(401, "invalid cron token")


def _format_brief_text(brief: dict) -> str:
    """Daily Brief JSON を text/plain に整形"""
    lines = [f"Daily Brief  {datetime.now().strftime('%Y-%m-%d (%a)')}", ""]

    schedule = brief.get("schedule") or []
    if schedule:
        lines.append("■ 今日の予定")
        for ev in schedule[:10]:
            title = ev.get("title", "(no title)")
            start = ev.get("start", "") or ""
            time_label = start.split("T")[1][:5] if "T" in start else "終日"
            lines.append(f"  ・{time_label}  {title[:80]}")
        lines.append("")

    backlog = brief.get("backlog") or []
    if backlog:
        lines.append("■ 今日のバックログ")
        for b in backlog[:8]:
            t = b.get("title") or b.get("text") or ""
            lines.append(f"  ・{t[:80]}")
        lines.append("")

    tomorrow = brief.get("schedule_tomorrow") or []
    if tomorrow:
        lines.append("■ 明日の予定")
        for ev in tomorrow[:6]:
            title = ev.get("title", "(no title)")
            start = ev.get("start", "") or ""
            time_label = start.split("T")[1][:5] if "T" in start else "終日"
            lines.append(f"  ・{time_label}  {title[:80]}")
        lines.append("")

    ai = brief.get("ai_brief") or ""
    if ai:
        lines.append("■ AI 問いかけ")
        lines.append(ai)

    return "\n".join(lines)


def _format_brief_html(brief: dict, text: str) -> str:
    """text 版から軽い HTML を作成 (Gmail での見やすさ用)"""
    body = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    body = body.replace("\n", "<br>")
    return f"""<!doctype html>
<html><body style="font-family: -apple-system, sans-serif; line-height: 1.6; max-width: 600px;">
<div style="white-space: pre-wrap;">{body}</div>
</body></html>"""


@router.post("/cron/notify-brief")
def notify_brief(
    engine: str = "claude",
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    _check_token(x_cron_token)
    api_key = os.environ.get("RESEND_API_KEY", "")
    to_email = os.environ.get("NOTIFY_EMAIL", "")
    from_email = os.environ.get("NOTIFY_FROM", "Koach OS <onboarding@resend.dev>")
    if not api_key or not to_email:
        raise HTTPException(503, "RESEND_API_KEY or NOTIFY_EMAIL not configured")

    from routers.daily_brief import daily_brief as gen_brief
    try:
        brief = gen_brief(engine=engine, model=None, force=True)
    except Exception as e:
        raise HTTPException(500, f"brief generation failed: {e}")

    text = _format_brief_text(brief)
    html = _format_brief_html(brief, text)
    subject = f"☀ Daily Brief {datetime.now().strftime('%m/%d (%a)')}"
    payload = json.dumps({
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": text,
        "html": html,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "koach-os/1.0 (+https://koach-os.vercel.app)",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            status = res.status
            body = res.read().decode("utf-8", errors="replace")[:200]
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise HTTPException(502, f"resend failed: HTTP {e.code} {body}")
    except Exception as e:
        raise HTTPException(502, f"resend failed: {e}")

    return {"ok": True, "resend_status": status, "chars_sent": len(text), "response": body}


_SECRET_NAME_HINTS = ("token", "credential", "secret", "_b64")


def _is_secret_file(name: str) -> bool:
    n = name.lower()
    return any(h in n for h in _SECRET_NAME_HINTS)


@router.post("/cron/snapshot-data")
def snapshot_data(
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    """data/ 配下を tar.gz → base64 で return。GitHub Actions が受け取って data-backup branch に commit する想定。"""
    _check_token(x_cron_token)

    if not DATA_DIR.exists():
        raise HTTPException(404, "DATA_DIR does not exist")

    buf = io.BytesIO()
    file_count = 0
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for p in sorted(DATA_DIR.rglob("*")):
            if not p.is_file():
                continue
            if _is_secret_file(p.name):
                continue
            tar.add(p, arcname=str(p.relative_to(DATA_DIR)))
            file_count += 1

    raw = buf.getvalue()
    return {
        "ok": True,
        "filename": "data-snapshot.tar.gz",
        "file_count": file_count,
        "size_bytes": len(raw),
        "data_base64": base64.b64encode(raw).decode("ascii"),
    }


# ---------------------------------------------------------------------------
# 翌日スケジュール自動チェック + 再編成提案 (Resend で送信)
# ---------------------------------------------------------------------------

@router.post("/cron/auto-reschedule")
def auto_reschedule(
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    """
    毎晩 23:00 JST 想定。
    - 翌日 (明日) の予定を Google Calendar から取得
    - メール由来の翌日締切を email_followups から拾う
    - AI に過密 / 衝突 / 再編成案を生成させる
    - Resend で NOTIFY_EMAIL へ送信
    """
    _check_token(x_cron_token)
    api_key = os.environ.get("RESEND_API_KEY", "")
    to_email = os.environ.get("NOTIFY_EMAIL", "")
    from_email = os.environ.get("NOTIFY_FROM", "Koach OS <onboarding@resend.dev>")
    if not api_key or not to_email:
        raise HTTPException(503, "RESEND_API_KEY or NOTIFY_EMAIL not configured")

    from datetime import timedelta as _td
    from data_manager import now_jst
    from gcal import is_configured, list_upcoming_events
    from router import call_ai as _call_ai

    now = now_jst()
    tomorrow = (now + _td(days=1)).date().isoformat()

    schedule = []
    if is_configured():
        try:
            week = list_upcoming_events(days_ahead=2) or []
            for ev in week:
                start = ev.get("start_iso", "")
                if start.startswith(tomorrow):
                    schedule.append({
                        "title": ev.get("title"),
                        "start": ev.get("start_iso"),
                        "end": ev.get("end_iso"),
                        "all_day": ev.get("all_day"),
                        "event_type": ev.get("event_type"),
                    })
        except Exception:
            pass

    followups_file = DATA_DIR / "email_followups.json"
    deadlines: list[dict] = []
    if followups_file.exists():
        try:
            fdata = json.loads(followups_file.read_text(encoding="utf-8"))
            for it in (fdata.get("items") or {}).values():
                if it.get("done_at"):
                    continue
                d = it.get("deadline_date") or ""
                if d == tomorrow:
                    deadlines.append({
                        "from": it.get("from", ""),
                        "subject": it.get("subject", "")[:80],
                        "summary": it.get("summary", "")[:80],
                        "urgency": it.get("urgency", "medium"),
                    })
        except Exception:
            pass

    prompt = (
        f"明日 ({tomorrow}) の予定と締切を見て、 過密 / 衝突 / 移動可能な再編成案を提案してください。\n\n"
        f"=== 明日の予定 ({len(schedule)} 件) ===\n"
        + (json.dumps(schedule, ensure_ascii=False, indent=2) if schedule else "(なし)")
        + f"\n\n=== 明日が締切のメール ({len(deadlines)} 件) ===\n"
        + (json.dumps(deadlines, ensure_ascii=False, indent=2) if deadlines else "(なし)")
        + "\n\n出力フォーマット (プレーンテキスト):\n"
          "■ サマリ (1-2 文)\n"
          "■ 衝突 / 過密の指摘 (箇条書き)\n"
          "■ 提案 (箇条書き、 各項目「何時のブロックを何時へ」を具体的に)\n"
          "■ 今夜のうちに済ませる準備物 (箇条書き、 なければ「なし」)\n"
    )
    try:
        ai_out = _call_ai(
            messages=[{"role": "user", "content": prompt}],
            system=(
                "あなたは志柿浩一郎の秘書 AI。 翌日の動きを俯瞰し、 衝突や過密を指摘し、 現実的な再配置を提案する。 "
                "迎合せず、 必要なら厳しい指摘もする。 抽象名詞「〜性」、 過度な絵文字、 です/ます調連打は避ける。"
            ),
            engine="claude",
            model="claude-opus-4-8",
            max_tokens=1500,
        )
    except Exception as e:
        ai_out = f"(AI 生成失敗: {e})"

    text = (
        f"翌日 ({tomorrow}) スケジュール調整候補\n\n"
        f"予定: {len(schedule)} 件 / 締切メール: {len(deadlines)} 件\n\n"
        f"{ai_out}\n"
    )
    html = (
        "<html><body style='font-family: -apple-system, sans-serif; line-height: 1.7; max-width: 640px;'>"
        f"<div style='white-space: pre-wrap;'>{text}</div></body></html>"
    )

    subject = f"📅 翌日スケジュール {tomorrow} ({len(schedule)} 件)"
    payload = json.dumps({
        "from": from_email,
        "to": [to_email],
        "subject": subject,
        "text": text,
        "html": html,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "koach-os/1.0 (+https://koach-os.vercel.app)",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            status = res.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        raise HTTPException(502, f"resend failed: HTTP {e.code} {body}")
    except Exception as e:
        raise HTTPException(502, f"resend failed: {e}")

    return {
        "ok": True,
        "schedule_count": len(schedule),
        "deadline_count": len(deadlines),
        "resend_status": status,
    }
