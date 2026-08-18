#!/usr/bin/env python3
"""
================================================================================
Filename:       get_5_random_tasks.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-08-18
Context:        http://trac.gafla.us.com/ticket/3589

Purpose:
    Connects to the Vikunja REST API, retrieves open/incomplete tasks, and
    selects a random subset (default 5) to display. Useful for the Daily
    Maintenance Mode (DMM), Morning meeting, or GTD backlog review when
    breaking procrastination or seeking unplanned quick wins.

    Supports filtering by project, priority level, label, or starred status,
    and formats output in plain text, Markdown, or JSON.

Secrets:
    VIKUNJA_API_TOKEN   (env var, from ~/.bashrc / vault-injected) - Vikunja REST API auth
    VIKUNJA_URL         (env var, optional; default http://todo.home.arpa) - not a secret

Usage:
    # Fetch 5 random tasks from across all open backlog tasks:
    ./get_5_random_tasks.py

    # Fetch 3 random tasks from the 'maintenance' project:
    ./get_5_random_tasks.py --project maintenance -n 3

    # Fetch 5 random tasks with priority 'high' or above:
    ./get_5_random_tasks.py --min-priority 3

    # Fetch only starred/favorite tasks:
    ./get_5_random_tasks.py --starred

    # Output in Markdown format (e.g. for meeting notes or wiki):
    ./get_5_random_tasks.py --markdown

    # Output as JSON for tooling / scripts:
    ./get_5_random_tasks.py --json

Arguments:
    -n, --count          Number of random tasks to select (default: 5).
    -p, --project        Filter tasks by project title (case-insensitive) or ID.
    -l, --label          Filter tasks by label title (case-insensitive).
    --priority           Filter by specific priority (now, urgent, high, medium, low, unset, or 0-5).
    --min-priority       Filter by minimum priority level (0-5).
    -s, --starred        Filter for starred / favorite tasks only.
    --due-only           Filter for tasks that have a due date.
    --overdue-only       Filter for tasks that are past their due date.
    --markdown, --md     Format output as Markdown.
    --json               Format output as JSON.
    --seed               Integer seed for reproducible random selection (testing).
    --host               Vikunja host URL (overrides VIKUNJA_URL env var).
    --token              Vikunja API token (overrides VIKUNJA_API_TOKEN env var).
    --public-url         Base public URL for task links (default: http://todo.gafla.us.com).

Exit Codes:
    0 - Success
    1 - API error, authentication failure, or invalid argument

Revision History:
    v1.0 (2026-08-18): Initial standardized implementation for Vikunja REST API.
                       Supports multi-page fetching, project/label/priority filtering,
                       Markdown/JSON outputs, and standard WWOS script headers. Trac #3589.

Notes:
    Always bump Version and add a Revision History entry when changing this file.
    WWOS:   http://wwos.home.arpa/index.php/Get_5_random_tasks.py
    GitHub: https://github.com/wrtaff/ansible-netbox/blob/master/scripts/get_5_random_tasks.py
================================================================================
"""

import argparse
import datetime
import json
import logging
import os
import random
import sys
from typing import Dict, List, Optional, Tuple

import requests

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
log = logging.getLogger("get_5_random_tasks")

PRIORITY_MAP = {
    "unset": 0,
    "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "urgent": 4,
    "now": 5,
}

PRIORITY_NAMES = {
    0: "unset",
    1: "low",
    2: "medium",
    3: "high",
    4: "urgent",
    5: "now",
}


def resolve_auth(host_arg: Optional[str] = None, token_arg: Optional[str] = None) -> Tuple[str, str]:
    """Resolve Vikunja host and API token from arguments, environment, or ~/.bashrc."""
    token = token_arg or os.getenv("VIKUNJA_API_TOKEN")
    if not token:
        bashrc_path = os.path.expanduser("~/.bashrc")
        if os.path.exists(bashrc_path):
            try:
                with open(bashrc_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if "export VIKUNJA_API_TOKEN=" in line:
                            token = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break
            except Exception as e:
                log.warning("Could not read ~/.bashrc: %s", e)

    if not token:
        sys.stderr.write("Error: VIKUNJA_API_TOKEN not set in environment or ~/.bashrc, and --token not passed.\n")
        sys.exit(1)

    host = host_arg or os.getenv("VIKUNJA_URL", "http://todo.home.arpa")
    return host.rstrip("/"), token


def get_all_projects(host: str, token: str) -> Dict[int, dict]:
    """Fetch all Vikunja projects, returning a mapping of project_id -> project dict."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    by_id = {}
    page = 1
    while page <= 50:
        try:
            resp = requests.get(f"{host}/api/v1/projects", headers=headers, params={"page": page}, timeout=15)
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            added = 0
            for p in batch:
                pid = p.get("id")
                if pid and pid > 0 and pid not in by_id:
                    by_id[pid] = p
                    added += 1
            if added == 0 or len(batch) < 50:
                break
            page += 1
        except Exception as e:
            log.warning("Error fetching projects page %d: %s", page, e)
            break
    return by_id


def resolve_project_filter(project_arg: str, projects_map: Dict[int, dict]) -> Optional[int]:
    """Resolve a project filter argument (name or ID) to a specific project ID."""
    if not project_arg:
        return None

    # Check if numeric ID
    try:
        pid = int(project_arg)
        if pid in projects_map:
            return pid
    except ValueError:
        pass

    # Match case-insensitively by title
    target_name = project_arg.strip().lower()
    exact = [pid for pid, p in projects_map.items() if p.get("title", "").strip().lower() == target_name]
    if len(exact) == 1:
        return exact[0]

    # Partial substring match
    subs = [pid for pid, p in projects_map.items() if target_name in p.get("title", "").strip().lower()]
    if len(subs) == 1:
        return subs[0]
    elif len(subs) > 1:
        matches = ", ".join(f"'{projects_map[i]['title']}' (id {i})" for i in subs)
        sys.stderr.write(f"Error: Ambiguous project '{project_arg}'. Matches: {matches}\n")
        sys.exit(1)

    valid = ", ".join(sorted(p.get("title", "") for p in projects_map.values()))
    sys.stderr.write(f"Error: Project '{project_arg}' not found. Available projects: {valid}\n")
    sys.exit(1)


def fetch_all_open_tasks(host: str, token: str) -> List[dict]:
    """Fetch all open (done = false) tasks across all pages from Vikunja."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    tasks = []
    page = 1
    max_pages = 100

    while page <= max_pages:
        try:
            resp = requests.get(
                f"{host}/api/v1/tasks",
                headers=headers,
                params={"filter": "done = false", "page": page},
                timeout=20,
            )
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            tasks.extend(batch)
            total_pages = int(resp.headers.get("x-pagination-total-pages", 1))
            if page >= total_pages:
                break
            page += 1
        except Exception as e:
            sys.stderr.write(f"Error fetching tasks from Vikunja API (page {page}): {e}\n")
            sys.exit(1)

    return tasks


def filter_tasks(
    tasks: List[dict],
    project_id: Optional[int] = None,
    priority_val: Optional[int] = None,
    min_priority_val: Optional[int] = None,
    starred_only: bool = False,
    label_filter: Optional[str] = None,
    due_only: bool = False,
    overdue_only: bool = False,
) -> List[dict]:
    """Apply client-side filters to task list."""
    filtered = []
    now_utc = datetime.datetime.now(datetime.timezone.utc)

    for t in tasks:
        # Project filter
        if project_id is not None and t.get("project_id") != project_id:
            continue

        # Priority filter (exact)
        t_priority = t.get("priority") or 0
        if priority_val is not None and t_priority != priority_val:
            continue

        # Minimum priority filter
        if min_priority_val is not None and t_priority < min_priority_val:
            continue

        # Starred / Favorite filter
        if starred_only and not t.get("is_favorite"):
            continue

        # Label filter
        if label_filter:
            t_labels = [l.get("title", "").lower() for l in (t.get("labels") or [])]
            target_lbl = label_filter.strip().lower()
            if not any(target_lbl in l for l in t_labels):
                continue

        # Due date filters
        due_str = t.get("due_date")
        has_due = bool(due_str and not due_str.startswith("0001-01-01"))

        if due_only and not has_due:
            continue

        if overdue_only:
            if not has_due:
                continue
            try:
                # Vikunja returns ISO timestamps e.g. 2026-08-15T12:00:00Z
                due_dt = datetime.datetime.fromisoformat(due_str.replace("Z", "+00:00"))
                if due_dt >= now_utc:
                    continue
            except Exception:
                continue

        filtered.append(t)

    return filtered


def format_text_output(
    selected_tasks: List[dict],
    total_open: int,
    total_matched: int,
    projects_map: Dict[int, dict],
    public_url_base: str,
) -> str:
    """Format tasks into a clean terminal-friendly text list."""
    lines = []
    lines.append(f"🎲 Selected {len(selected_tasks)} Random Task(s) (Matched: {total_matched} | Total Open: {total_open})")
    lines.append("=" * 80)

    for i, t in enumerate(selected_tasks, 1):
        tid = t.get("id")
        title = t.get("title", "(No title)")
        pid = t.get("project_id")
        proj_name = projects_map.get(pid, {}).get("title", f"Project {pid}")
        pri_val = t.get("priority", 0)
        pri_name = PRIORITY_NAMES.get(pri_val, str(pri_val))
        starred = "⭐ Yes" if t.get("is_favorite") else "No"
        
        due_str = t.get("due_date", "")
        if due_str and not due_str.startswith("0001-01-01"):
            due_display = due_str[:10]
        else:
            due_display = "None"

        labels = t.get("labels") or []
        label_names = ", ".join(f"*{l.get('title')}" for l in labels) if labels else "None"
        task_url = f"{public_url_base.rstrip('/')}/tasks/{tid}"

        lines.append(f"{i}. [#{tid}] {title}")
        lines.append(f"   Project:   {proj_name} (id {pid})")
        lines.append(f"   Priority:  {pri_name.upper()} ({pri_val}) | Starred: {starred} | Due: {due_display}")
        lines.append(f"   Labels:    {label_names}")
        lines.append(f"   Link:      {task_url}")
        lines.append("")

    return "\n".join(lines).strip()


def format_markdown_output(
    selected_tasks: List[dict],
    total_open: int,
    total_matched: int,
    projects_map: Dict[int, dict],
    public_url_base: str,
) -> str:
    """Format tasks into Markdown with clickable links and metadata."""
    lines = []
    lines.append(f"### 🎲 {len(selected_tasks)} Random Task(s) (Matched: {total_matched} / Total Open: {total_open})")
    lines.append("")

    for i, t in enumerate(selected_tasks, 1):
        tid = t.get("id")
        title = t.get("title", "(No title)")
        pid = t.get("project_id")
        proj_name = projects_map.get(pid, {}).get("title", f"Project {pid}")
        pri_val = t.get("priority", 0)
        pri_name = PRIORITY_NAMES.get(pri_val, str(pri_val))
        starred = " ⭐" if t.get("is_favorite") else ""

        due_str = t.get("due_date", "")
        if due_str and not due_str.startswith("0001-01-01"):
            due_display = due_str[:10]
        else:
            due_display = "None"

        labels = t.get("labels") or []
        label_names = ", ".join(f"`{l.get('title')}`" for l in labels) if labels else "none"
        task_url = f"{public_url_base.rstrip('/')}/tasks/{tid}"

        lines.append(f"{i}. **[{title}]({task_url})** (#{tid}){starred}")
        lines.append(f"   - **Project:** `{proj_name}` | **Priority:** `{pri_name}` | **Due:** `{due_display}`")
        lines.append(f"   - **Labels:** {label_names}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Select and display random open tasks from Vikunja for daily review and quick wins.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-n", "--count", "-c", type=int, default=5, help="Number of random tasks to select (default: 5)")
    parser.add_argument("-p", "--project", help="Filter tasks by project title (case-insensitive) or ID")
    parser.add_argument("-l", "--label", help="Filter tasks by label title (case-insensitive)")
    parser.add_argument(
        "--priority",
        help="Filter by exact priority (now, urgent, high, medium, low, unset, or 0-5)",
    )
    parser.add_argument(
        "--min-priority",
        type=int,
        choices=[0, 1, 2, 3, 4, 5],
        help="Filter by minimum priority level (0=unset to 5=now)",
    )
    parser.add_argument("-s", "--starred", action="store_true", help="Filter for starred / favorite tasks only")
    parser.add_argument("--due-only", action="store_true", help="Filter for tasks that have a due date")
    parser.add_argument("--overdue-only", action="store_true", help="Filter for tasks past their due date")
    parser.add_argument("--markdown", "--md", action="store_true", help="Output as Markdown")
    parser.add_argument("--json", action="store_true", help="Output raw JSON array of selected tasks")
    parser.add_argument("--seed", type=int, help="Random seed for deterministic selection (testing)")
    parser.add_argument("--host", help="Vikunja host URL (overrides VIKUNJA_URL env var)")
    parser.add_argument("--token", help="Vikunja API token (overrides VIKUNJA_API_TOKEN env var)")
    parser.add_argument(
        "--public-url",
        default="http://todo.gafla.us.com",
        help="Base public URL for task links (default: http://todo.gafla.us.com)",
    )

    args = parser.parse_args()

    if args.count < 1:
        sys.stderr.write("Error: --count must be at least 1.\n")
        sys.exit(1)

    # Resolve Priority argument if provided
    priority_val = None
    if args.priority is not None:
        p_str = args.priority.strip().lower()
        if p_str.isdigit():
            priority_val = int(p_str)
        elif p_str in PRIORITY_MAP:
            priority_val = PRIORITY_MAP[p_str]
        else:
            valid_p = ", ".join(PRIORITY_MAP.keys())
            sys.stderr.write(f"Error: Invalid priority '{args.priority}'. Valid options: {valid_p} or 0-5.\n")
            sys.exit(1)

    # Auth & API Setup
    host, token = resolve_auth(args.host, args.token)

    # Fetch projects map for naming and project filtering
    projects_map = get_all_projects(host, token)
    project_id = resolve_project_filter(args.project, projects_map) if args.project else None

    # Fetch all open tasks
    all_open_tasks = fetch_all_open_tasks(host, token)
    total_open = len(all_open_tasks)

    # Filter tasks
    matched_tasks = filter_tasks(
        tasks=all_open_tasks,
        project_id=project_id,
        priority_val=priority_val,
        min_priority_val=args.min_priority,
        starred_only=args.starred,
        label_filter=args.label,
        due_only=args.due_only,
        overdue_only=args.overdue_only,
    )
    total_matched = len(matched_tasks)

    if not matched_tasks:
        if args.json:
            print("[]")
        else:
            print(f"No matching open tasks found (Total open tasks in backlog: {total_open}).")
        return

    # Random selection
    if args.seed is not None:
        random.seed(args.seed)

    sample_size = min(args.count, total_matched)
    selected_tasks = random.sample(matched_tasks, sample_size)

    # Output formatting
    if args.json:
        print(json.dumps(selected_tasks, indent=2))
    elif args.markdown:
        print(format_markdown_output(selected_tasks, total_open, total_matched, projects_map, args.public_url))
    else:
        print(format_text_output(selected_tasks, total_open, total_matched, projects_map, args.public_url))


if __name__ == "__main__":
    main()
