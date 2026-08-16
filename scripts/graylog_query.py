#!/usr/bin/env python3
"""
================================================================================
Filename:       graylog_query.py
Version:        1.1
Author:         Claude Code
Last Modified:  2026-08-07
Context:        http://trac.gafla.us.com/ticket/3439

Purpose:
    Query Graylog via REST API, replacing the manual CSV export workflow.
    Used by the logfile-reviewer skill and other Pops agents.
    Uses an expiring runtime token cache and retries one HTTP 401 with the
    current Vault value.

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
import tempfile
import time
import requests
import urllib3
from typing import Optional

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

GRAYLOG_URL = os.getenv("GRAYLOG_URL", "http://graylog.home.arpa:9000")
GRAYLOG_API_TOKEN = os.getenv("GRAYLOG_API_TOKEN")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, ".."))
_VAULT_FILE = os.path.join(_SCRIPT_DIR, "..", "vault.yml")
_VAULT_KEY = "graylog_pops_admin_token"
_CACHE_MAX_AGE_SECONDS = 3600
_CACHE_DIR = os.getenv(
    "POPS_SECRET_CACHE_DIR",
    os.path.join(tempfile.gettempdir(), f"pops-secrets-{os.getuid()}"),
)
_TOKEN_CACHE_FILE = os.path.join(_CACHE_DIR, "graylog-token.json")


def _get_token_from_cache() -> Optional[str]:
    if os.path.exists(_TOKEN_CACHE_FILE):
        try:
            if time.time() - os.path.getmtime(_TOKEN_CACHE_FILE) > _CACHE_MAX_AGE_SECONDS:
                _clear_token_cache()
                return None
            with open(_TOKEN_CACHE_FILE, "r") as f:
                return json.load(f).get("token") or None
        except Exception:
            _clear_token_cache()
            pass
    return None


def _get_token_from_vault() -> Optional[str]:
    if not os.path.exists(_VAULT_FILE):
        return None
    try:
        result = subprocess.run(
            ["ansible-vault", "view", _VAULT_FILE],
            cwd=_PROJECT_ROOT, capture_output=True, text=True, check=True,
        )
        for line in result.stdout.splitlines():
            if _VAULT_KEY in line and ":" in line:
                return line.split(":", 1)[1].strip().strip("'").strip('"')
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    except Exception as e:
        print(f"DEBUG: vault error: {e}", file=sys.stderr)
    return None


def _save_token_to_cache(token: str) -> None:
    try:
        os.makedirs(_CACHE_DIR, mode=0o700, exist_ok=True)
        os.chmod(_CACHE_DIR, 0o700)
        fd, temporary_path = tempfile.mkstemp(dir=_CACHE_DIR)
        with os.fdopen(fd, "w") as f:
            json.dump({"token": token, "cached_at": int(time.time())}, f)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, _TOKEN_CACHE_FILE)
    except Exception as e:
        print(f"DEBUG: could not cache token: {e}", file=sys.stderr)


def _clear_token_cache() -> None:
    try:
        os.remove(_TOKEN_CACHE_FILE)
    except FileNotFoundError:
        pass


def get_token(force_refresh: bool = False) -> str:
    global GRAYLOG_API_TOKEN
    env_token = os.getenv("GRAYLOG_API_TOKEN")
    if GRAYLOG_API_TOKEN and not force_refresh:
        return GRAYLOG_API_TOKEN
    if not force_refresh:
        GRAYLOG_API_TOKEN = _get_token_from_cache() or env_token
    if GRAYLOG_API_TOKEN and not force_refresh:
        return GRAYLOG_API_TOKEN
    vault_token = _get_token_from_vault()
    if vault_token:
        GRAYLOG_API_TOKEN = vault_token
        _save_token_to_cache(GRAYLOG_API_TOKEN)
        return GRAYLOG_API_TOKEN
    if env_token:
        GRAYLOG_API_TOKEN = env_token
        return GRAYLOG_API_TOKEN
    raise RuntimeError(
        "Graylog API token not found. Set GRAYLOG_API_TOKEN env var or ensure "
        f"'{_VAULT_KEY}' is present in vault.yml."
    )


def _graylog_get(endpoint: str, timeout: int, params: Optional[dict] = None):
    headers = {"Accept": "application/json", "X-Requested-By": "pops-agent"}
    response = requests.get(
        endpoint, auth=(get_token(), "token"), headers=headers,
        params=params, timeout=timeout, verify=False,
    )
    if response.status_code != 401:
        return response

    # A cache is never authoritative. Retry once with the current Vault value.
    _clear_token_cache()
    response = requests.get(
        endpoint, auth=(get_token(force_refresh=True), "token"), headers=headers,
        params=params, timeout=timeout, verify=False,
    )
    return response


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
    endpoint = f"{GRAYLOG_URL}/api/search/universal/relative"

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

        resp = _graylog_get(endpoint, timeout=30, params=params)
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
    try:
        resp = _graylog_get(f"{GRAYLOG_URL}/api/system", timeout=10)
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
