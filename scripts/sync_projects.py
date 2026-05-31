#!/usr/bin/env python3
"""
ローカル各プロジェクトの git log を読んで koach-os の /projects に反映。

使い方:
    python3 scripts/sync_projects.py                # 全部同期
    python3 scripts/sync_projects.py --dry-run      # 送らずに表示
    python3 scripts/sync_projects.py --api http://localhost:8000  # ローカル backend

cron / launchd で 1 時間おきに回すと、/projects ダッシュボードが常に最新。
Claude Code の Stop hook から叩いても良い (1 セッション終わるたびに sync)。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_API = "https://backend-production-0987.up.railway.app"


def expand(path: str) -> Path:
    return Path(os.path.expanduser(path)).resolve()


def git_info(local_path: Path) -> dict | None:
    """git log -1 から sha / message / date / author を取得。
    git repo でなければ None。"""
    if not local_path.exists() or not (local_path / ".git").exists():
        return None
    try:
        # SHA
        sha = subprocess.check_output(
            ["git", "log", "-1", "--format=%H"],
            cwd=str(local_path),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        # Message (subject 1行)
        message = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"],
            cwd=str(local_path),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        # Date ISO 8601
        date = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI"],
            cwd=str(local_path),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        # Author email
        author = subprocess.check_output(
            ["git", "log", "-1", "--format=%ae"],
            cwd=str(local_path),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        # Uncommitted (porcelain で行数)
        porcelain = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=str(local_path),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        uncommitted = len([l for l in porcelain.splitlines() if l.strip()])
        return {
            "last_commit_sha": sha[:12],
            "last_commit_message": message[:160],
            "last_commit_date": date,
            "last_commit_author": author,
            "uncommitted_changes": uncommitted,
            "source": "git",
        }
    except Exception as e:
        print(f"  git error: {e}", file=sys.stderr)
        return None


def fetch_projects(api: str) -> list[dict]:
    req = urllib.request.Request(f"{api}/api/projects")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["projects"]


def post_sync(api: str, items: list[dict]) -> dict:
    body = json.dumps({"items": items}).encode()
    req = urllib.request.Request(
        f"{api}/api/projects/sync",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=DEFAULT_API, help="backend base URL")
    parser.add_argument("--dry-run", action="store_true", help="送信せず表示のみ")
    parser.add_argument("--only", help="特定 project id だけ (カンマ区切り可)")
    args = parser.parse_args()

    print(f"→ fetching project list from {args.api}")
    try:
        projects = fetch_projects(args.api)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    only_ids = set(args.only.split(",")) if args.only else None

    items = []
    for p in projects:
        pid = p["id"]
        if only_ids and pid not in only_ids:
            continue
        lp = p.get("local_path", "")
        if not lp:
            continue
        path = expand(lp)
        print(f"  {pid}: {path}")
        info = git_info(path)
        if info is None:
            print("    (not a git repo or missing)")
            continue
        item = {"id": pid, **info}
        print(f"    sha={info['last_commit_sha']} | {info['last_commit_message']}")
        print(f"    date={info['last_commit_date']} dirty={info['uncommitted_changes']}")
        items.append(item)

    if not items:
        print("\n何も同期対象なし (local_path が無い or git repo じゃない)")
        return

    if args.dry_run:
        print(f"\n[dry-run] 送らない。{len(items)} 件を sync する予定だった")
        return

    print(f"\n→ POST /api/projects/sync ({len(items)} 件)")
    result = post_sync(args.api, items)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
