"""
Cron endpoints — external scheduled triggers (GitHub Actions etc.)

- POST /api/cron/notify-brief   : Daily Brief を生成して Discord webhook へ送信
- POST /api/cron/snapshot-data  : data/ 配下を tar.gz → base64 で return

Auth: header `X-Cron-Token` が env CRON_TOKEN と一致しないと 401。
"""

import os
import io
import json
import base64
import tarfile
import urllib.request
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException

from data_manager import DATA_DIR

router = APIRouter()


def _check_token(token: str | None) -> None:
    expected = os.environ.get("CRON_TOKEN", "")
    if not expected:
        raise HTTPException(503, "CRON_TOKEN not configured")
    if token != expected:
        raise HTTPException(401, "invalid cron token")


def _format_brief_for_discord(brief: dict) -> str:
    """Daily Brief JSON を Discord 用テキストに整形 (2000 文字制限)"""
    lines = [f"☀️ **Daily Brief — {datetime.now().strftime('%Y-%m-%d (%a)')}**", ""]

    schedule = brief.get("schedule") or []
    if schedule:
        lines.append("**📅 今日の予定**")
        for ev in schedule[:8]:
            title = ev.get("title", "(no title)")
            start = ev.get("start", "") or ""
            time_label = start.split("T")[1][:5] if "T" in start else "終日"
            lines.append(f"  • {time_label}  {title[:60]}")
        lines.append("")

    backlog = brief.get("backlog") or []
    if backlog:
        lines.append("**📋 今日のバックログ**")
        for b in backlog[:6]:
            t = b.get("title") or b.get("text") or ""
            lines.append(f"  • {t[:60]}")
        lines.append("")

    tomorrow = brief.get("schedule_tomorrow") or []
    if tomorrow:
        lines.append("**📅 明日の予定**")
        for ev in tomorrow[:4]:
            title = ev.get("title", "(no title)")
            start = ev.get("start", "") or ""
            time_label = start.split("T")[1][:5] if "T" in start else "終日"
            lines.append(f"  • {time_label}  {title[:60]}")
        lines.append("")

    ai = brief.get("ai_brief") or ""
    if ai:
        lines.append("**🧭 AI 問いかけ**")
        lines.append(ai[:600])

    text = "\n".join(lines)
    if len(text) > 1900:
        text = text[:1900] + "\n…(truncated)"
    return text


@router.post("/cron/notify-brief")
def notify_brief(
    engine: str = "claude",
    x_cron_token: str | None = Header(None, alias="X-Cron-Token"),
):
    _check_token(x_cron_token)
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook_url:
        raise HTTPException(503, "DISCORD_WEBHOOK_URL not configured")

    from routers.daily_brief import daily_brief as gen_brief
    try:
        brief = gen_brief(engine=engine, model=None, force=True)
    except Exception as e:
        raise HTTPException(500, f"brief generation failed: {e}")

    text = _format_brief_for_discord(brief)
    payload = json.dumps({"content": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as res:
            status = res.status
    except Exception as e:
        raise HTTPException(502, f"discord post failed: {e}")

    return {"ok": True, "discord_status": status, "chars_sent": len(text)}


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
