#!/usr/bin/env python3
"""
================================================================================
Filename:       gmail_push_to_task.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-11
Context:        http://trac.gafla.us.com/ticket/3589

Purpose:
    Sweep Gmail for messages labeled 'push-to-task', create a Vikunja task for
    each (with the email linked in Markdown so it is clickable), then remove
    'push-to-task' and apply 'task-got-pushed' so each message is processed
    exactly once. Designed to run unattended from cron.

    Tasks default to the Vikunja 'Inbox' project (the GTD inbox, sorted during
    the Weekly Review / Morning meeting). If a message also carries a nested
    label 'push-to-task/<project>', <project> is matched to an EXISTING Vikunja
    project (case-insensitive) and is NEVER created; on no match it falls back
    to Inbox.

Secrets:
    VIKUNJA_API_TOKEN   (env var, from ~/.bashrc / vault-injected) - Vikunja REST API auth
    Gmail OAuth2 token  (managed by scripts/google_workspace_manager.py:
                         CREDENTIALS_FILE + cached token; needs gmail.modify scope)
                         - Gmail read + label modify
    VIKUNJA_URL         (env var, optional; default http://todo.home.arpa) - not a secret

Usage:
    ./gmail_push_to_task.py                       # process up to --max labeled messages
    ./gmail_push_to_task.py --dry-run --verbose   # preview, no writes
    ./gmail_push_to_task.py --default-project Inbox --max 50
    # cron (every 15 min):
    #   */15 * * * * /home/will/ansible-netbox/.venv/bin/python3 \
    #       /home/will/ansible-netbox/scripts/gmail_push_to_task.py >> /var/log/gmail_push_to_task.log 2>&1

Revision History:
    1.0 - Initial version. Trac #3589.

NOTES:
    Always bump Version and add a Revision History entry when changing this file.
    WWOS:   http://wwos.home.arpa/index.php/Gmail_push_to_task.py
    GitHub: https://github.com/wrtaff/ansible-netbox/blob/master/scripts/gmail_push_to_task.py
================================================================================
"""
import os
import sys
import argparse
import logging

import requests
from googleapiclient.discovery import build

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from scripts import google_workspace_manager as gwm  # noqa: E402  (Gmail auth + API)

DEFAULT_LABEL = "push-to-task"
DONE_LABEL = "task-got-pushed"
DEFAULT_PROJECT = "Inbox"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("gmail_push_to_task")


# --- Vikunja -----------------------------------------------------------------

def vikunja_env():
    """Resolve Vikunja host + token (env first, then ~/.bashrc like the MCP servers)."""
    token = os.getenv("VIKUNJA_API_TOKEN")
    if not token:
        bashrc = os.path.expanduser("~/.bashrc")
        if os.path.exists(bashrc):
            with open(bashrc) as f:
                for line in f:
                    if "export VIKUNJA_API_TOKEN=" in line:
                        token = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break
    if not token:
        raise SystemExit("VIKUNJA_API_TOKEN not set (env or ~/.bashrc).")
    host = os.getenv("VIKUNJA_URL", "http://todo.home.arpa").rstrip("/")
    return host, token


def _vikunja_get(host, token, path, params=None):
    r = requests.get(f"{host}/api/v1{path}",
                     headers={"Authorization": f"Bearer {token}"}, params=params or {})
    r.raise_for_status()
    return r.json()


def get_all_projects(host, token):
    """Fetch real Vikunja projects, de-duplicated; saved filters (negative ids) excluded."""
    by_id = {}
    page = 1
    while page <= 50:  # hard safety cap
        batch = _vikunja_get(host, token, "/projects", {"page": page})
        if not batch:
            break
        added = 0
        for p in batch:
            if p.get("id") not in by_id:
                by_id[p["id"]] = p
                added += 1
        if added == 0 or len(batch) < 50:
            break
        page += 1
    return [p for p in by_id.values() if (p.get("id") or 0) > 0]


def resolve_project_id(name, projects):
    """
    Match a project NAME to an existing project id. Match only, never create.
    Returns (project_id, matched_title) or (None, None). Numeric input passes through.
    """
    try:
        return int(name), None
    except (ValueError, TypeError):
        pass
    n = str(name).strip().lower()
    active = [p for p in projects if not p.get("is_archived")]
    exact = [p for p in active if str(p.get("title", "")).strip().lower() == n]
    if len(exact) == 1:
        return exact[0]["id"], exact[0]["title"]
    subs = [p for p in active if n in str(p.get("title", "")).strip().lower()]
    if len(subs) == 1:
        return subs[0]["id"], subs[0]["title"]
    return None, None


def create_task(host, token, project_id, title, description):
    """Create a Vikunja task via PUT /api/v1/projects/{id}/tasks. Returns the task JSON."""
    r = requests.put(
        f"{host}/api/v1/projects/{project_id}/tasks",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"title": title, "description": description},
    )
    r.raise_for_status()
    return r.json()


# --- Gmail -------------------------------------------------------------------

def gmail_service():
    return build("gmail", "v1", credentials=gwm.get_creds())


def gmail_labels(service):
    return service.users().labels().list(userId="me").execute().get("labels", [])


def ensure_label(service, name):
    """Return the id of the Gmail label `name`, creating it if it does not exist."""
    for l in gmail_labels(service):
        if l["name"] == name:
            return l["id"]
    created = service.users().labels().create(
        userId="me",
        body={"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"},
    ).execute()
    log.info("Created Gmail label '%s' (%s)", name, created["id"])
    return created["id"]


# --- Sweep -------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="Sweep Gmail 'push-to-task' messages into Vikunja tasks.")
    ap.add_argument("--label", default=DEFAULT_LABEL, help="Gmail trigger label (default: push-to-task)")
    ap.add_argument("--done-label", default=DONE_LABEL, help="Label applied after pushing (default: task-got-pushed)")
    ap.add_argument("--default-project", default=DEFAULT_PROJECT, help="Vikunja project when no sub-label (default: Inbox)")
    ap.add_argument("--max", type=int, default=50, help="Max messages per run")
    ap.add_argument("--dry-run", action="store_true", help="Preview only; no Vikunja or label writes")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.verbose:
        log.setLevel(logging.DEBUG)

    host, token = vikunja_env()
    projects = get_all_projects(host, token)
    service = gmail_service()
    id_to_name = {l["id"]: l["name"] for l in gmail_labels(service)}

    resp = service.users().messages().list(
        userId="me", q=f"label:{args.label}", maxResults=args.max).execute()
    msgs = resp.get("messages", [])
    if not msgs:
        log.info("No messages labeled '%s'. Nothing to do.", args.label)
        return 0

    if not args.dry_run:
        ensure_label(service, args.done_label)

    pushed = 0
    for ref in reversed(msgs):  # oldest-first
        m = service.users().messages().get(
            userId="me", id=ref["id"], format="metadata",
            metadataHeaders=["Subject", "From", "Date"]).execute()
        headers = {h["name"]: h["value"] for h in m.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "(no subject)")
        sender = headers.get("From", "")
        date = headers.get("Date", "")
        mid = m["id"]
        link = f"https://mail.google.com/mail/u/0/#all/{mid}"

        # A nested label 'push-to-task/<project>' overrides the default project.
        prefix = f"{args.label}/"
        sub_label_name = None
        sub_project = None
        for lid in m.get("labelIds", []):
            ln = id_to_name.get(lid, "")
            if ln.startswith(prefix):
                sub_label_name = ln
                sub_project = ln[len(prefix):]
                break

        proj_name = sub_project or args.default_project
        pid, matched = resolve_project_id(proj_name, projects)
        if pid is None:
            log.warning("No Vikunja project matches '%s' (msg %s); falling back to Inbox.", proj_name, mid)
            pid, matched = resolve_project_id("Inbox", projects)
            proj_name = "Inbox"

        title = subject
        description = f"From: {sender}\nDate: {date}\n\n[{subject}]({link})"

        log.info("%s msg=%s subject=%r -> project=%s (id=%s)",
                 "[dry-run]" if args.dry_run else "push", mid, subject[:60], matched or proj_name, pid)

        if args.dry_run:
            continue

        try:
            task = create_task(host, token, pid, title, description)
        except Exception as e:
            log.error("Failed to create Vikunja task for msg %s: %s", mid, e)
            continue

        remove = [args.label] + ([sub_label_name] if sub_label_name else [])
        try:
            gwm.gmail_modify_labels(message_id=mid, add_labels=[args.done_label],
                                    remove_labels=remove, output_format="json")
        except Exception as e:
            log.error("Task #%s created but relabel failed for msg %s: %s", task.get("id"), mid, e)
            continue

        pushed += 1
        log.info("Pushed msg %s -> Vikunja task #%s (%s); relabeled.", mid, task.get("id"), matched or proj_name)

    log.info("Done. Pushed %d task(s)%s.", pushed, " (dry-run)" if args.dry_run else "")
    return 0


if __name__ == "__main__":
    sys.exit(main())
