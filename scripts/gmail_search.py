#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/gmail_search.py
Version:        1.0
Author:         Claude Sonnet 4.6
Last Modified:  2026-06-30
Context:        http://trac.gafla.us.com/ticket/3760

Purpose:
    Fast Gmail search from the terminal using Gmail query syntax.
    Returns matching messages with date, sender, subject, snippet, and URL
    without requiring the Gmail web UI to load.

Usage:
    python3 gmail_search.py "subject:invoice from:bank"
    python3 gmail_search.py "label:*inbucket is:unread" --limit 20
    python3 gmail_search.py "from:noreply@example.com" --json

    Query strings use standard Gmail search syntax (same as the web UI search box).

Revision History:
    v1.0 (2026-06-30): Initial version. Trac #3760.

Secrets:
    token.pickle    (scripts/ local file) -- OAuth 2.0 user credentials (via google_workspace_manager.get_creds)
    credentials.json (scripts/ local file) -- Google OAuth 2.0 client secrets (via google_workspace_manager.get_creds)

Notes:
    Reuses OAuth credentials managed by google_workspace_manager.py.
    Uses Gmail API format='metadata' to fetch From/Subject headers without
    downloading full message bodies.
================================================================================
"""

import os
import sys

# --- BOOTSTRAP CHECK ---
# Re-exec under the project .venv if google libs are not importable.
def bootstrap():
    try:
        import googleapiclient  # noqa: F401
    except ImportError:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        venv_python = os.path.join(project_root, '.venv', 'bin', 'python3')
        if os.path.exists(venv_python) and sys.executable != venv_python:
            os.execv(venv_python, [venv_python] + sys.argv)
        else:
            print("CRITICAL: Google Workspace dependencies missing and .venv not found.", file=sys.stderr)
            print("Run 'pip install -r requirements.txt' in the project root.", file=sys.stderr)
            sys.exit(1)

bootstrap()

import argparse
import json
from datetime import datetime, timezone

from googleapiclient.discovery import build
from google_workspace_manager import get_creds


def get_header(headers, name):
    for h in headers:
        if h['name'].lower() == name.lower():
            return h['value']
    return ''


def search_gmail(query, limit=10):
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)

    results = service.users().messages().list(
        userId='me', q=query, maxResults=limit
    ).execute()

    stubs = results.get('messages', [])
    if not stubs:
        return []

    messages = []
    for stub in stubs:
        msg = service.users().messages().get(
            userId='me',
            id=stub['id'],
            format='metadata',
            metadataHeaders=['From', 'Subject', 'Date']
        ).execute()

        headers = msg.get('payload', {}).get('headers', [])
        ts_ms = int(msg.get('internalDate', 0))
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)

        messages.append({
            'id': msg['id'],
            'date': dt.strftime('%Y-%m-%d %H:%M UTC'),
            'from': get_header(headers, 'From'),
            'subject': get_header(headers, 'Subject'),
            'snippet': msg.get('snippet', ''),
            'url': f'https://mail.google.com/mail/u/0/#all/{msg["id"]}',
        })

    return messages


def print_text(messages):
    for i, m in enumerate(messages, 1):
        print(f"[{i}] {m['date']}  {m['from']}")
        print(f"    Subject: {m['subject']}")
        print(f"    {m['snippet'][:120]}")
        print(f"    {m['url']}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Search Gmail from the terminal using Gmail query syntax.'
    )
    parser.add_argument('query', help='Gmail search query (e.g. "subject:invoice from:bank")')
    parser.add_argument('--limit', type=int, default=10, metavar='N',
                        help='Maximum number of results (default: 10)')
    parser.add_argument('--json', dest='as_json', action='store_true',
                        help='Output as JSON instead of plain text')
    args = parser.parse_args()

    try:
        messages = search_gmail(args.query, limit=args.limit)
    except Exception as e:
        print(f'Error: {e}', file=sys.stderr)
        sys.exit(1)

    if not messages:
        print('No messages found.')
        return

    if args.as_json:
        print(json.dumps(messages, indent=2))
    else:
        print(f'{len(messages)} result(s) for: {args.query}\n')
        print_text(messages)


if __name__ == '__main__':
    main()
