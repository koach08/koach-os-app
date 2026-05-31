#!/usr/bin/env python3
"""
~/Desktop 配下 (デフォルト) の git repo を再帰スキャン → koach-os に候補として登録。

使い方:
    python3 scripts/discover_local_projects.py
    python3 scripts/discover_local_projects.py --root ~/Desktop --max-depth 4
    python3 scripts/discover_local_projects.py --dry-run

検出ルール:
- ディレクトリに .git があれば git repo として候補化
- node_modules / .next / venv / __pycache__ / .git は再帰しない
- 既登録の project (github_url or local_path 一致) は除外 (backend 側でも判定)

候補は koach-os の /api/projects/candidates に蓄積され、/projects ページで承認/却下する。
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
DEFAULT_ROOTS = ["~/Desktop", "~/investment-app"]
SKIP_DIRS = {"node_modules", ".next", ".venv", "venv", "__pycache__", ".git", "dist", "build", ".turbo", ".cache"}


def expand(p: str) -> Path:
    return Path(os.path.expanduser(p)).resolve()


def find_repos(root: Path, max_depth: int = 4) -> list[Path]:
    """root 配下の .git ディレクトリを持つ場所を列挙 (max_depth 階層まで)"""
    results: list[Path] = []
    if not root.exists():
        return results

    def walk(d: Path, depth: int):
        if depth > max_depth:
            return
        try:
            entries = list(d.iterdir())
        except PermissionError:
            return
        names = {e.name for e in entries}
        if ".git" in names:
            results.append(d)
            return  # repo 内は降りない
        for e in entries:
            if e.is_dir() and e.name not in SKIP_DIRS and not e.name.startswith("."):
                walk(e, depth + 1)

    walk(root, 0)
    return results


def repo_meta(p: Path) -> dict:
    """git remote / log / package files から情報抽出"""
    info: dict = {
        "name": p.name,
        "local_path": str(p).replace(os.path.expanduser("~"), "~"),
        "github_url": "",
        "last_commit_date": "",
        "last_commit_message": "",
        "file_count": 0,
        "has_package_json": (p / "package.json").exists(),
        "has_pyproject": (p / "pyproject.toml").exists() or (p / "requirements.txt").exists(),
        "has_cargo_toml": (p / "Cargo.toml").exists(),
        "notes": "",
    }
    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=str(p),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        # SSH を https に正規化
        if remote.startswith("git@github.com:"):
            remote = "https://github.com/" + remote.split(":", 1)[1].rstrip(".git")
        elif remote.endswith(".git"):
            remote = remote[:-4]
        info["github_url"] = remote
    except Exception:
        pass
    try:
        info["last_commit_date"] = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI"],
            cwd=str(p),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        info["last_commit_message"] = subprocess.check_output(
            ["git", "log", "-1", "--format=%s"],
            cwd=str(p),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()[:160]
    except Exception:
        pass
    try:
        # 概算 file count (高速、tracked + untracked)
        out = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=str(p),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        info["file_count"] = len(out.splitlines())
    except Exception:
        pass
    return info


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--root", action="append", help="scan root (複数指定可)")
    parser.add_argument("--max-depth", type=int, default=4)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    roots = args.root or DEFAULT_ROOTS
    print(f"→ scanning roots: {roots} (max depth {args.max_depth})")

    all_repos: list[Path] = []
    for r in roots:
        rp = expand(r)
        if not rp.exists():
            print(f"  skip (not found): {rp}")
            continue
        repos = find_repos(rp, args.max_depth)
        print(f"  {rp}: {len(repos)} repos")
        all_repos.extend(repos)

    if not all_repos:
        print("repo が 1 つも見つからない")
        return

    items = []
    for repo in all_repos:
        meta = repo_meta(repo)
        items.append(meta)
        print(f"  • {meta['name']:30s} {meta['github_url'] or '(no remote)'}")

    if args.dry_run:
        print(f"\n[dry-run] 送らない。{len(items)} repo を候補化する予定だった")
        print(json.dumps(items[:2], ensure_ascii=False, indent=2))
        return

    body = json.dumps({"items": items}).encode()
    req = urllib.request.Request(
        f"{args.api}/api/projects/discover/local",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            result = json.loads(r.read())
            print(f"\n→ POST /api/projects/discover/local")
            print(json.dumps(result, ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as e:
        print(f"ERROR {e.code}: {e.read().decode()[:300]}", file=sys.stderr)


if __name__ == "__main__":
    main()
