#!/usr/bin/env python3
"""
================================================================================
Filename:       create_vikunja_task.py
Version:        1.6
Author:         Gemini CLI
Last Modified:  2026-09-29
Context:        http://trac.home.arpa/ticket/3321, http://trac.gafla.us.com/ticket/4768

Purpose:
    Creates a new task in a Vikunja instance. This script is designed to be 
    portable and can be used locally or on remote hosts with Gemini CLI. It 
    supports setting the task title, description, project ID, "favorite" 
    status, and labels.

Secrets:
    VIKUNJA_API_TOKEN   (environment) — Bearer token for Vikunja REST API

Revision History:
    v1.6 (2026-09-29): Implement Vikunja Todo Standard: due_date normalization
                       (America/New_York to UTC Z), description auto-conversion
                       to HTML via markdown, Inbox project warning, and HTTP 400
                       field hints (Trac #4768 WP-2).
    v1.5 (2026-04-16): Refactored create_task to raise exceptions instead of calling
                       sys.exit(1) to support integration into MCP servers.
                       Updated header with Trac ticket link per WWOS standards.
    v1.4 (2026-03-03): Added support for setting task due dates via --due argument.
    v1.3 (2026-01-30): Fixed label attachment logic: Labels are now added via a
                       separate API call after task creation, per Vikunja API.
================================================================================
"""
import os
import sys
import json
import argparse
import urllib.request
import urllib.error
import ssl
import datetime


def normalize_due_date(due_date):
    """
    Normalize due_date input into an RFC3339/ISO-8601 UTC timestamp ending in 'Z'.
    Interprets naive dates and date-only strings in America/New_York.
    Returns normalized_due_date string or raises ValueError on invalid format.
    """
    if not due_date or not str(due_date).strip():
        return None
    s = str(due_date).strip()
    try:
        import zoneinfo
        tz_ny = zoneinfo.ZoneInfo("America/New_York")
    except Exception:
        tz_ny = datetime.timezone(datetime.timedelta(hours=-5))

    try:
        if s.endswith("Z") or s.endswith("z"):
            dt = datetime.datetime.fromisoformat(s[:-1] + "+00:00")
        else:
            dt = datetime.datetime.fromisoformat(s)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz_ny)

        utc_dt = dt.astimezone(datetime.timezone.utc)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        raise ValueError(f"Invalid due_date format: '{due_date}'. Use ISO-8601 (e.g. 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SSZ').")


def format_description_for_vikunja(desc):
    """
    Converts Markdown description to HTML so Vikunja's TipTap editor renders clickable links.
    Preserves existing HTML.
    """
    if not desc or not desc.strip():
        return desc
    s = desc.strip()
    if s.startswith("<p>") or "</a>" in s or "</div>" in s or "<ul>" in s:
        return desc
    try:
        import markdown
        return markdown.markdown(s)
    except Exception:
        return desc


def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def get_all_labels(host, token):
    url = f"{host}/api/v1/labels"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=10) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Warning: Could not fetch labels: {e}")
    return []

def create_label(host, token, title):
    url = f"{host}/api/v1/labels"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = json.dumps({"title": title}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=10) as response:
            if response.status in (200, 201):
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Warning: Could not create label '{title}': {e}")
    return None

def add_label_to_task(host, token, task_id, label_id):
    url = f"{host}/api/v1/tasks/{task_id}/labels"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = json.dumps({"label_id": label_id}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=10) as response:
            response.read()
            if response.status in (200, 201):
                return True
    except Exception as e:
        print(f"Warning: Could not attach label ID {label_id} to task {task_id}: {e}")
    return False

def create_task(title, description="", project_id=1, is_favorite=True, host="http://todo.home.arpa", token=None, labels=None, due_date=None):
    if not token:
        token = os.getenv("VIKUNJA_API_TOKEN")
    
    if not token:
        print("Error: VIKUNJA_API_TOKEN environment variable not set and --token not provided.")
        sys.exit(1)

    if project_id == 1:
        print("Warning: Task filed in Inbox (project_id=1). Domain projects: board (65), church (56), eldercare (63), finance (35), food (3), geeks (74), healthcare (14), maintenance (9), persdev (61), recreation (66), sysadmin (64).")

    if due_date:
        due_date = normalize_due_date(due_date)

    if description:
        description = format_description_for_vikunja(description)

    # Resolve Labels
    resolved_labels = []
    if labels:
        print("Resolving labels...", end=" ", flush=True)
        existing_labels = get_all_labels(host, token)
        # Create a mapping for case-insensitive lookup
        label_map = {l['title'].lower(): l for l in existing_labels}
        
        for label_name in labels:
            existing = label_map.get(label_name.lower())
            if existing:
                resolved_labels.append({"id": existing['id'], "title": existing['title']})
            else:
                print(f"(Creating new label '{label_name}')...", end=" ", flush=True)
                new_label = create_label(host, token, label_name)
                if new_label:
                    resolved_labels.append({"id": new_label['id'], "title": new_label['title']})
        print("Done.")

    url = f"{host}/api/v1/projects/{project_id}/tasks"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "title": title,
        "description": description or "",
        "is_favorite": is_favorite
    }
    if due_date:
        payload["due_date"] = due_date
    
    # NOTE: Labels are NOT added here in the create payload anymore.
    
    json_payload = json.dumps(payload).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=json_payload, headers=headers, method="PUT")
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=10) as response:
            if response.status in (200, 201):
                result = json.loads(response.read().decode('utf-8'))
                task_id = result.get('id')
                print(f"Success: Task created with ID {task_id}")
                print(f"Title: {result.get('title')}")
                print(f"Link: {host}/tasks/{task_id}")
                
                # Attach Labels
                if resolved_labels:
                    print("Attaching labels...", end=" ", flush=True)
                    count = 0
                    for label in resolved_labels:
                        if add_label_to_task(host, token, task_id, label['id']):
                            count += 1
                    print(f"Attached {count}/{len(resolved_labels)} labels.")
                return result
            else:
                raise Exception(f"Unexpected status code {response.status}: {response.read().decode('utf-8')}")

    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        if e.code == 400:
            raise Exception(f"HTTP Error 400: {e.reason} - {body}. Hint: check due_date format (must be ISO-8601 UTC) or project ID.")
        raise Exception(f"HTTP Error {e.code}: {e.reason} - {body}")
    except urllib.error.URLError as e:
        raise Exception(f"URL Error: {e.reason}")

def main():
    parser = argparse.ArgumentParser(description="Create a task in Vikunja.")
    parser.add_argument("--title", required=True, help="Task title")
    parser.add_argument("--description", default="", help="Task description (Markdown supported)")
    parser.add_argument("--project-id", type=int, default=1, help="Project ID (Default: 1 for Inbox)")
    parser.add_argument("--no-favorite", action="store_true", help="Do not mark as favorite (Default: Favorite)")
    parser.add_argument("--host", default="http://todo.home.arpa", help="Vikunja host URL")
    parser.add_argument("--token", help="API Token (overrides VIKUNJA_API_TOKEN env var)")
    parser.add_argument("--due", help="Due date (ISO format, e.g., 2026-03-04T13:00:00)")
    
    args = parser.parse_args()
    
    # Parse labels from title
    words = args.title.split()
    labels = [w[1:] for w in words if w.startswith('*')]
    clean_title = ' '.join([w for w in words if not w.startswith('*')])
    
    try:
        create_task(
            title=clean_title,
            description=args.description,
            project_id=args.project_id,
            is_favorite=not args.no_favorite,
            host=args.host.rstrip('/'),
            token=args.token,
            labels=labels,
            due_date=args.due
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
