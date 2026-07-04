#!/usr/bin/env python3
# ==============================================================================
# Script:     piwigo_manager.py
# Purpose:    Administer the Piwigo photo gallery (http://piwigo.home.arpa)
#             via its ws.php web API: create/list users, trigger directory
#             sync, and query gallery status. Built for the 'agent' service
#             account so automated workflows don't need the human login.
# Secrets:    PIWIGO_USER, PIWIGO_PASSWORD (env vars) — credentials for the
#             account performing the action (human 'will' or service 'agent').
#             Never hardcode; never store the password itself outside
#             Vaultwarden.
# ==============================================================================
# Revision History:
#   2026-07-04  Claude (Sonnet 5)  Initial creation: session login, user
#                                  creation, sync trigger, status query
# ==============================================================================

import os
import sys
import json
import argparse
import requests

BASE_URL = os.environ.get("PIWIGO_URL", "http://piwigo.home.arpa")
WS_URL = f"{BASE_URL}/ws.php"


def api_call(session, method, params=None, files=None):
    # Piwigo's ws.php only reads 'format' from the query string ($_GET), never
    # from the POST body -- it must go in the URL or the response silently
    # falls back to XML instead of JSON.
    payload = {"method": method}
    if params:
        payload.update(params)
    resp = session.post(WS_URL, params={"format": "json"}, data=payload, files=files, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if data.get("stat") != "ok":
        raise RuntimeError(f"{method} failed: {data.get('message', data)}")
    return data.get("result")


def login(username, password):
    session = requests.Session()
    api_call(session, "pwg.session.login", {"username": username, "password": password})
    return session


def cmd_status(session, args):
    result = api_call(session, "pwg.session.getStatus")
    print(json.dumps(result, indent=2))


def cmd_list_users(session, args):
    result = api_call(session, "pwg.users.getList")
    for u in result.get("users", []):
        print(f"{u['id']:>4}  {u['username']:<20} status={u['status']}")


def cmd_create_user(session, args):
    if args.new_password == args.password:
        sys.exit("Refusing to create a user with the same password as the login account — use a distinct credential per account.")
    pwg_token = api_call(session, "pwg.session.getStatus")["pwg_token"]
    result = api_call(session, "pwg.users.add", {
        "username": args.username,
        "password": args.new_password,
        "email": args.email or "",
        "pwg_token": pwg_token,
    })
    user_id = result["id"]
    if args.status:
        api_call(session, "pwg.users.setInfo", {"user_id": user_id, "status": args.status, "pwg_token": pwg_token})
    print(f"Created user '{args.username}' (id={user_id}, status={args.status or 'normal'})")


def cmd_sync(session, args):
    # Directory sync has no first-class ws.php method; this hits the same
    # admin endpoint the web UI uses. Always simulate first.
    params = {
        "page": "site_update",
        "site": 1,
        "sync": "files",
        "display_info": 1,
        "simulate": 1 if not args.commit else 0,
    }
    resp = session.get(f"{BASE_URL}/admin.php", params=params, timeout=60)
    resp.raise_for_status()
    mode = "REAL SYNC" if args.commit else "SIMULATION"
    print(f"[{mode}] request sent — check {BASE_URL}/admin.php?page=site_update&site=1 for results")


def main():
    parser = argparse.ArgumentParser(description="Administer Piwigo via its ws.php API")
    parser.add_argument("--user", default=os.environ.get("PIWIGO_USER"), help="Login username (default: $PIWIGO_USER)")
    parser.add_argument("--password", default=os.environ.get("PIWIGO_PASSWORD"), help="Login password (default: $PIWIGO_PASSWORD)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="Show current session status").set_defaults(func=cmd_status)
    sub.add_parser("list-users", help="List all Piwigo users").set_defaults(func=cmd_list_users)

    p_create = sub.add_parser("create-user", help="Create a new Piwigo user")
    p_create.add_argument("username")
    p_create.add_argument("--new-password", required=True, help="Password for the NEW account (must differ from the login account's password)")
    p_create.add_argument("--email")
    p_create.add_argument("--status", choices=["webmaster", "admin", "normal", "guest"], default="normal")
    p_create.set_defaults(func=cmd_create_user)

    p_sync = sub.add_parser("sync", help="Trigger a filesystem synchronize")
    p_sync.add_argument("--commit", action="store_true", help="Run for real (default is simulate-only)")
    p_sync.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    if not args.user or not args.password:
        sys.exit("Set PIWIGO_USER / PIWIGO_PASSWORD env vars or pass --user/--password (login credentials).")

    session = login(args.user, args.password)
    args.func(session, args)


if __name__ == "__main__":
    main()
