#!/bin/bash
# safe_deploy.sh — koach-os 用 Vercel deploy wrapper
#
# Why: 2026-06-03 に Claude が link 外れた状態で `vercel --prod` を実行 →
#      cwd フォルダ名 "frontend" から推測されて EGAKU の Vercel project
#      (名前が "frontend") に koach-os が上書きデプロイされる事故が発生。
#      fal.ai 課金 802 ドルの二次被害も発生。
#
# Rules:
#   1. 引数で expected project name を必ず指定 (例: koach-os)
#   2. cwd の .vercel/project.json の projectName が一致しなければ即 abort
#   3. cwd を表示してから 3 秒 sleep して人間が確認できる猶予を作る
#
# Usage:
#   cd /path/to/frontend
#   bash safe_deploy.sh koach-os
#
# Claude へ: vercel --prod を裸で叩かない。必ずこのスクリプト経由。

set -e

EXPECTED="$1"
if [ -z "$EXPECTED" ]; then
    echo "ERROR: usage: $0 <expected-vercel-project-name>"
    echo "       例: $0 koach-os"
    exit 2
fi

CWD="$(pwd)"
PJ_FILE=".vercel/project.json"

if [ ! -f "$PJ_FILE" ]; then
    echo "❌ ABORT: $CWD/.vercel/project.json が存在しません"
    echo "   裸の vercel --prod を叩いていません。先に明示 link してください:"
    echo "     vercel link --project $EXPECTED --yes"
    exit 3
fi

ACTUAL=$(python3 -c "import json,sys; print(json.load(open('$PJ_FILE')).get('projectName',''))" 2>/dev/null || echo "")

if [ "$ACTUAL" != "$EXPECTED" ]; then
    echo "❌ ABORT: project mismatch"
    echo "   期待: $EXPECTED"
    echo "   実際: '$ACTUAL' ($CWD/$PJ_FILE)"
    echo ""
    echo "   このまま deploy すると別 project ($ACTUAL) に上書きされます。"
    echo "   先に明示 link し直してください:"
    echo "     rm -rf .vercel && vercel link --project $EXPECTED --yes"
    exit 4
fi

echo "✓ Project: $EXPECTED  (.vercel/project.json 確認済み)"
echo "✓ CWD:     $CWD"
echo ""
echo "3 秒後に deploy 開始 (中断するなら Ctrl+C)..."
sleep 3

echo ""
echo "→ vercel --prod --yes"
exec vercel --prod --yes
