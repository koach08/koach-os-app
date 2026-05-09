#!/usr/bin/env python3
"""
Koach OS — Google OAuth Setup (Calendar + Gmail)
===================================================
One-time OAuth2 authorization for:
- Google Calendar (read+write)
- Gmail (read-only)

Prerequisites:
1. Go to https://console.cloud.google.com/
2. Create a project (or use existing)
3. Enable BOTH:
   - Google Calendar API
   - Gmail API
4. Create OAuth2 credentials (Desktop application)
5. Download as "credentials.json" to the koach-os-app/ directory
6. Add yourself as a test user (OAuth consent screen)

Usage:
    python scripts/setup_gcal.py

After successful auth, the script prints token.json contents.
For Railway deployment, copy that JSON into env var GOOGLE_TOKEN_JSON.
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

    print("Opening browser for Google authorization...")
    print("Scopes: Calendar (read+write) + Gmail (read-only)")
    print()

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
    creds = flow.run_local_server(port=0)

    token_json = creds.to_json()
    TOKEN_FILE.write_text(token_json)
    print(f"Authorization successful! Token saved to: {TOKEN_FILE}")
    print()

    # Test Calendar
    from gcal import get_events, list_recent_emails
    events = get_events()
    print(f"Today's events: {len(events)}")
    for e in events:
        print(f"  - {e['start'][:16] if 'T' in e['start'] else 'All day'}: {e['summary']}")
    print()

    # Test Gmail
    try:
        emails = list_recent_emails(days=1, max_results=3)
        print(f"Recent emails (last 1 day): {len(emails)}")
        for em in emails:
            print(f"  - {em['from'][:40]}: {em['subject'][:60]}")
    except Exception as e:
        print(f"Gmail test failed: {e}")
    print()

    # For Railway: print env var to copy
    print("=" * 60)
    print("For Railway deployment, set this env var:")
    print("=" * 60)
    print()
    print(f"GOOGLE_TOKEN_JSON='{token_json}'")
    print()
    print("Set via:")
    print("  railway variables --service backend --set 'GOOGLE_TOKEN_JSON=...'")


if __name__ == "__main__":
    main()
