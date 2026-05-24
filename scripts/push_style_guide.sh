#!/bin/bash
# 志柿スタイルガイドを Koach OS backend に push する。
# 使い方: ./scripts/push_style_guide.sh
# iCloud の koach_style_guide_v2.md を読んで backend に置き換える。

set -e

GUIDE_PATH="$HOME/Library/Mobile Documents/com~apple~CloudDocs/Shigaki-style-guide/koach_style_guide_v2.md"
BACKEND_URL="${BACKEND_URL:-https://backend-production-0987.up.railway.app}"

if [ ! -f "$GUIDE_PATH" ]; then
  echo "ERROR: $GUIDE_PATH not found" >&2
  exit 1
fi

CONTENT=$(cat "$GUIDE_PATH")
SIZE=$(wc -c < "$GUIDE_PATH" | tr -d ' ')

echo "Push $SIZE bytes from $GUIDE_PATH"
echo "→ $BACKEND_URL/api/personas/style-profile"

python3 - <<EOF
import json, sys, urllib.request
url = "$BACKEND_URL/api/personas/style-profile"
body = json.dumps({"content": open("$GUIDE_PATH", encoding="utf-8").read()}).encode("utf-8")
req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
with urllib.request.urlopen(req) as r:
    print("✓", r.read().decode())
EOF
