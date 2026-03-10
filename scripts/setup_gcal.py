#!/usr/bin/env python3
"""
Koach OS — Google Calendar Setup
===================================
One-time OAuth2 authorization for Google Calendar read access.

Prerequisites:
1. Go to https://console.cloud.google.com/
2. Create a project (or use existing)
3. Enable "Google Calendar API"
4. Create OAuth2 credentials (Desktop application)
5. Download as "credentials.json" to the koach-os-app/ directory

Usage:
    python scripts/setup_gcal.py
"""

import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from gcal import CREDENTIALS_FILE, TOKEN_FILE, SCOPES


def main():
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("ERROR: google-auth-oauthlib not installed.")
        print("Run: pip install google-auth-oauthlib google-api-python-client")
        sys.exit(1)

    if not CREDENTIALS_FILE.exists():
        print(f"ERROR: {CREDENTIALS_FILE} not found.")
        print()
        print("Setup steps:")
        print("1. Go to https://console.cloud.google.com/")
        print("2. Create/select a project")
        print("3. Enable 'Google Calendar API'")
        print("4. Go to Credentials -> Create Credentials -> OAuth 2.0 Client ID")
        print("5. Application type: Desktop application")
        print("6. Download JSON and save as: credentials.json")
        print(f"   Save to: {CREDENTIALS_FILE}")
        sys.exit(1)

    print("Opening browser for Google Calendar authorization...")
    print("(Read-only access)")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(creds.to_json())
    print(f"Authorization successful! Token saved to: {TOKEN_FILE}")
    print()

    # Test
    from gcal import get_events
    events = get_events()
    print(f"Today's events: {len(events)}")
    for e in events:
        print(f"  - {e['start'][:16] if 'T' in e['start'] else 'All day'}: {e['summary']}")


if __name__ == "__main__":
    main()
