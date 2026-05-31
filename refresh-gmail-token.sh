#!/bin/bash
# Refresh Google OAuth token and push to Railway (slot 1 or 2).
# Run weekly (Test users mode expires every 7 days) or whenever Gmail/Calendar returns 'invalid_grant'.
#
# Prerequisites (one-time):
#   - credentials.json in the project root (Google Cloud OAuth Desktop client)
#   - python3
#   - railway login (CLI authenticated)
#
# Usage:
#   ./refresh-gmail-token.sh          # slot 1 = japanesebusinessman4 (default)
#   ./refresh-gmail-token.sh 1        # slot 1
#   ./refresh-gmail-token.sh 2        # slot 2 = kshgks59
#   ./refresh-gmail-token.sh both     # both slots in sequence

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

SLOT_ARG="${1:-1}"

if [ ! -f credentials.json ]; then
    echo "ERROR: credentials.json not found in $PROJECT_DIR"
    echo "Download from Google Cloud Console → OAuth client (Desktop) and save as credentials.json"
    exit 1
fi

# Setup venv if missing
if [ ! -d venv ]; then
    echo "→ Creating venv..."
    python3 -m venv venv
    venv/bin/pip install -q google-auth-oauthlib google-api-python-client pyyaml python-dotenv
fi

refresh_one() {
    local SLOT="$1"
    local ENV_NAME
    local TOKEN_FILE_NAME
    if [ "$SLOT" = "1" ]; then
        ENV_NAME="GOOGLE_TOKEN_JSON"
        TOKEN_FILE_NAME="token.json"
        echo ""
        echo "═══ Slot 1 (japanesebusinessman4) ═══"
    else
        ENV_NAME="GOOGLE_TOKEN_JSON_${SLOT}"
        TOKEN_FILE_NAME="token_${SLOT}.json"
        echo ""
        echo "═══ Slot ${SLOT} (kshgks59 for slot 2) ═══"
    fi

    echo "→ Starting OAuth flow for slot ${SLOT} (browser will open)..."
    echo "  Sign in with the appropriate Google account when the browser opens."

    SLOT="$SLOT" TOKEN_FILE_NAME="$TOKEN_FILE_NAME" venv/bin/python -u <<'PYEOF'
import os, sys
sys.path.insert(0, ".")
from google_auth_oauthlib.flow import InstalledAppFlow
from gcal import CREDENTIALS_FILE, SCOPES

slot = int(os.environ["SLOT"])
token_file_name = os.environ["TOKEN_FILE_NAME"]

# Fixed port 8765 — must be added to Google Cloud Console Authorized redirect URIs:
#   http://localhost:8765/
FIXED_PORT = 8765

flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
creds = flow.run_local_server(port=FIXED_PORT, open_browser=True, prompt="consent", access_type="offline")

from pathlib import Path
Path(token_file_name).write_text(creds.to_json())
print(f"AUTH OK → {token_file_name}")
PYEOF

    if [ ! -f "$TOKEN_FILE_NAME" ]; then
        echo "ERROR: ${TOKEN_FILE_NAME} not generated"
        exit 1
    fi

    echo "→ Pushing token to Railway (${ENV_NAME})..."
    TOKEN=$(cat "$TOKEN_FILE_NAME")

    if ! railway whoami >/dev/null 2>&1; then
        echo "ERROR: Railway CLI not authenticated. Run: railway login"
        echo "Token saved locally at: $PROJECT_DIR/$TOKEN_FILE_NAME"
        echo "Paste into Railway dashboard env var ${ENV_NAME} manually."
        exit 1
    fi

    railway link --project koach-os-api --service backend >/dev/null 2>&1 || true
    railway variables --service backend --set "${ENV_NAME}=$TOKEN" >/dev/null

    # Also set _B64 variant (some code paths prefer that)
    if command -v base64 >/dev/null 2>&1; then
        B64=$(echo -n "$TOKEN" | base64 | tr -d '\n')
        railway variables --service backend --set "${ENV_NAME}_B64=$B64" >/dev/null
        echo "✓ Set ${ENV_NAME} + ${ENV_NAME}_B64 on Railway"
    else
        echo "✓ Set ${ENV_NAME} on Railway"
    fi
}

case "$SLOT_ARG" in
    1) refresh_one 1 ;;
    2) refresh_one 2 ;;
    both) refresh_one 1; refresh_one 2 ;;
    *) echo "Usage: $0 [1|2|both]"; exit 1 ;;
esac

echo ""
echo "✓ Done. Railway will auto-restart the service in ~30 seconds."
echo "  Test: curl https://backend-production-0987.up.railway.app/api/gmail/slots"
