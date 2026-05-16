#!/bin/bash
# Refresh Google OAuth token and push to Railway.
# Run weekly (or whenever Gmail/Calendar features return 'invalid_grant').
#
# Prerequisites (one-time):
#   - credentials.json in the project root (Google Cloud OAuth Desktop client)
#   - python3 + google-auth-oauthlib installed
#   - railway login (CLI authenticated)
#
# Usage:
#   ./refresh-gmail-token.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

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

echo "→ Starting OAuth flow (browser will open)..."
venv/bin/python -u <<'PYEOF'
import sys
sys.path.insert(0, ".")
from google_auth_oauthlib.flow import InstalledAppFlow
from gcal import CREDENTIALS_FILE, SCOPES, TOKEN_FILE
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(("localhost", 0))
port = sock.getsockname()[1]
sock.close()

flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
creds = flow.run_local_server(port=port, open_browser=True, prompt="consent", access_type="offline")
TOKEN_FILE.write_text(creds.to_json())
print("AUTH OK")
PYEOF

if [ ! -f token.json ]; then
    echo "ERROR: token.json not generated"
    exit 1
fi

echo "→ Pushing token to Railway..."
TOKEN=$(cat token.json)

# Check railway CLI auth
if ! railway whoami >/dev/null 2>&1; then
    echo "ERROR: Railway CLI not authenticated. Run: railway login"
    echo "Token is saved locally at: $PROJECT_DIR/token.json"
    echo "You can paste it into Railway dashboard env var GOOGLE_TOKEN_JSON manually."
    exit 1
fi

railway link --project koach-os-api >/dev/null 2>&1 || true
railway variables --service backend --set "GOOGLE_TOKEN_JSON=$TOKEN" >/dev/null

echo "✓ Token refreshed and pushed to Railway."
echo "✓ Railway will auto-restart the service in ~30 seconds."
