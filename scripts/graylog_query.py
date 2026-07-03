#!/usr/bin/env python3
"""
================================================================================
Filename:       graylog_query.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-05-14
Context:        http://trac.gafla.us.com/ticket/3439

Purpose:
    Query Graylog via REST API, replacing the manual CSV export workflow.
    Used by the logfile-reviewer skill and other Pops agents.

Usage:
    python3 graylog_query.py query "source:router" [--hours 24] [--limit 500]
    python3 graylog_query.py recent [--hours 1] [--limit 100]
    python3 graylog_query.py test
================================================================================
"""
import os
import sys
import json
import subprocess
import argparse
import requests
import urllib3
from typing import Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GRAYLOG_URL = os.getenv("GRAYLOG_URL", "http://graylog.home.arpa:9000")
GRAYLOG_API_TOKEN = os.getenv("GRAYLOG_API_TOKEN")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_TMP_TOKEN_FILE = os.path.join(_SCRIPT_DIR, "..", "tmp", "graylog_token.txt")
_VAULT_FILE = os.path.join(_SCRIPT_DIR, "..", "vault.yml")
_VAULT_KEY = "graylog_pops_admin_token"


def _get_token_from_tmp() -> Optional[str]:
    if os.path.exists(_TMP_TOKEN_FILE):
        try:
            with open(_TMP_TOKEN_FILE, "r") as f:
                return f.read().strip() or None
        except Exception:
            pass
    return None


def _get_token_from_vault() -> Optional[str]:
    if not os.path.exists(_VAULT_FILE):
        return None
    try:
        result = subprocess.run(
            ["ansible-vault", "view", _VAULT_FILE],
            capture_output=True, text=True, check=True,
        )
        for line in result.stdout.splitlines():
            if _VAULT_KEY in line and ":" in line:
                return line.split(":", 1)[1].strip().strip("'").strip('"')
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    except Exception as e:
        print(f"DEBUG: vault error: {e}", file=sys.stderr)
    return None


def _save_token_to_tmp(token: str) -> None:
    try:
        os.makedirs(os.path.dirname(_TMP_TOKEN_FILE), exist_ok=True)
        with open(_TMP_TOKEN_FILE, "w") as f:
            f.write(token)
        os.chmod(_TMP_TOKEN_FILE, 0o600)
    except Exception as e:
        print(f"DEBUG: could not cache token: {e}", file=sys.stderr)


def get_token() -> str:
    global GRAYLOG_API_TOKEN
    if GRAYLOG_API_TOKEN:
        return GRAYLOG_API_TOKEN
    GRAYLOG_API_TOKEN = _get_token_from_tmp()
    if GRAYLOG_API_TOKEN:
        return GRAYLOG_API_TOKEN
    GRAYLOG_API_TOKEN = _get_token_from_vault()
    if GRAYLOG_API_TOKEN:
        _save_token_to_tmp(GRAYLOG_API_TOKEN)
        return GRAYLOG_API_TOKEN
    raise RuntimeError(
        "Graylog API token not found. Set GRAYLOG_API_TOKEN env var or ensure "
        f"'{_VAULT_KEY}' is present in vault.yml."
    )


def query_messages(
    query: str = "*",
    hours: int = 24,
    limit: int = 500,
    fields: Optional[list] = None,
) -> list[dict]:
    """
    Search Graylog messages. Returns a list of message dicts.

    Args:
        query:  Graylog query string (e.g. "source:router AND level:3")
        hours:  Look-back window in hours
        limit:  Max messages to return (paginated internally if needed)
        fields: Optional list of fields to return; None = all fields
    """
    token = get_token()
    endpoint = f"{GRAYLOG_URL}/api/search/universal/relative"
    headers = {"Accept": "application/json", "X-Requested-By": "pops-agent"}
    auth = (token, "token")

    all_messages = []
    page_size = min(limit, 500)  # Graylog hard cap per request
    offset = 0

    while len(all_messages) < limit:
        params = {
            "query": query,
            "range": hours * 3600,
            "limit": min(page_size, limit - len(all_messages)),
            "offset": offset,
        }
        if fields:
            params["fields"] = ",".join(fields)

        resp = requests.get(
            endpoint, auth=auth, headers=headers, params=params, timeout=30, verify=False
        )
        resp.raise_for_status()

        data = resp.json()
        batch = data.get("messages", [])
        if not batch:
            break

        all_messages.extend(m.get("message", m) for m in batch)
        offset += len(batch)

        total = data.get("total_results", 0)
        if offset >= total:
            break

    return all_messages


def test_connection() -> bool:
    """Ping the Graylog API and return True if reachable and authenticated."""
    token = get_token()
    try:
        resp = requests.get(
            f"{GRAYLOG_URL}/api/system",
            auth=(token, "token"),
            headers={"Accept": "application/json", "X-Requested-By": "pops-agent"},
            timeout=10,
            verify=False,
        )
        if resp.status_code == 200:
            info = resp.json()
            print(f"Connected: Graylog {info.get('version', '?')} at {GRAYLOG_URL}")
            return True
        else:
            print(f"Auth failed: HTTP {resp.status_code}", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Connection error: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(description="Query Graylog REST API")
    sub = parser.add_subparsers(dest="cmd")

    q = sub.add_parser("query", help="Run a Graylog query")
    q.add_argument("search", help="Graylog query string")
    q.add_argument("--hours", type=int, default=24, help="Look-back window (default: 24)")
    q.add_argument("--limit", type=int, default=500, help="Max messages (default: 500)")
    q.add_argument("--json", action="store_true", help="Output raw JSON")

    r = sub.add_parser("recent", help="Fetch recent messages (query=*)")
    r.add_argument("--hours", type=int, default=1)
    r.add_argument("--limit", type=int, default=100)
    r.add_argument("--json", action="store_true")

    sub.add_parser("test", help="Test connectivity and auth")

    args = parser.parse_args()

    if args.cmd == "test":
        sys.exit(0 if test_connection() else 1)

    elif args.cmd in ("query", "recent"):
        search = getattr(args, "search", "*")
        msgs = query_messages(search, hours=args.hours, limit=args.limit)
        if args.json:
            print(json.dumps(msgs, indent=2))
        else:
            print(f"Returned {len(msgs)} messages (last {args.hours}h, query={search!r})\n")
            for m in msgs:
                ts = m.get("timestamp", "")
                src = m.get("source", "")
                msg = m.get("message", "")
                print(f"[{ts}][{src}] {msg[:200]}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
