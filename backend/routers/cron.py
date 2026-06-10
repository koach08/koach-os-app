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
