#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/vikunja/server.py
Version:        1.8
Author:         Gemini CLI
Last Modified:  2026-09-23
Context:        http://trac.gafla.us.com/ticket/3321

Purpose:
    Model Context Protocol (MCP) server for Vikunja integration.
    Wraps scripts/create_vikunja_task.py and scripts/create_trac_from_vikunja.py
    to provide tools for managing Vikunja tasks and linking them to Trac.

Revision History:
    v1.8 (2026-09-23): Add CircuitBreaker and retry-with-confirmation pattern for task creation
                       to reconcile unconfirmed tasks and prevent duplicate task creation on timeout (resolves #4198).
                       Context: http://trac.gafla.us.com/ticket/3321
    v1.7 (2026-09-23): Automatically resolve label names to numeric IDs in vikunja_search_tasks
                       filter expressions (supporting '=', '!=', 'in', 'not in', and quoted names).
                       Propagate API JSON error body on non-2xx responses.
                       Context: http://trac.gafla.us.com/ticket/3321
    v1.6 (2026-08-21): Fix vikunja_get_tasks_by_priority starred/favorite query by removing
                       invalid server-side is_favorite filter and adding pagination. Add
                       priority parameter to vikunja_update_task and preserve existing
                       fields on update to prevent silent field resets.
                       Context: http://trac.gafla.us.com/ticket/4372
    v1.5 (2026-08-20): Automatically convert Markdown descriptions to HTML so links
                       render as clickable hyperlinks in the Vikunja web UI.
    v1.4 (2026-07-07): vikunja_create_trac_ticket now builds a properly cited MoinMoin
                       wiki link (task title as link text, WWOS-style <ref> citation)
                       back to the Vikunja task instead of a bare URL, and converts the
                       embedded task description from HTML to wiki markup. component is
                       now optional and auto-guessed from the task's Vikunja project name,
                       falling back to 'recreation' with a note when unconfident.
    v1.3 (2026-06-11): Added vikunja_list_projects tool. vikunja_create_task now accepts a
                       'project' NAME that is matched (case-insensitive) to an existing
                       project; it never creates a project. Context: http://trac.gafla.us.com/ticket/3584
    v1.2 (2026-06-05): Added vikunja_get_tasks_by_priority tool with named/numeric priority support.
    v1.1 (2026-04-16): Updated header with Trac ticket link per WWOS standards.
    v1.0 (2026-04-16): Initial implementation.

Notes:
    Always bump the version number when modifying this file and annotate 
    the changes in the Revision History section.
================================================================================
"""
import os
import sys
import re
import html
import logging
import json
import time
import threading
import datetime
import urllib.error
from typing import Optional, List, Union

# Add project root to path to allow importing from scripts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP
from scripts import create_vikunja_task as cvt
from scripts import create_trac_from_vikunja as ctfv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/vikunja_mcp.log',
    filemode='a'
)
logger = logging.getLogger("vikunja-mcp")

# Initialize FastMCP server
mcp = FastMCP("vikunja-server")

logger.info("Initializing Vikunja MCP Server v1.8")


class CircuitBreaker:
    """
    Thread-safe Circuit Breaker pattern to protect against persistent API failures/timeouts.
    States: CLOSED (normal), OPEN (fast-fail), HALF_OPEN (canary probe).
    """
    def __init__(self, failure_threshold: int = 3, recovery_timeout: float = 15.0, name: str = "vikunja"):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.failure_count = 0
        self.last_state_change = 0.0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.lock = threading.Lock()

    def can_execute(self) -> bool:
        with self.lock:
            now = time.time()
            if self.state == "CLOSED":
                return True
            elif self.state == "OPEN":
                if now - self.last_state_change >= self.recovery_timeout:
                    logger.info(f"CircuitBreaker[{self.name}]: Transitioning from OPEN to HALF_OPEN (probing recovery)")
                    self.state = "HALF_OPEN"
                    self.last_state_change = now
                    return True
                return False
            elif self.state == "HALF_OPEN":
                return True
            return True

    def record_success(self):
        with self.lock:
            if self.state != "CLOSED":
                logger.info(f"CircuitBreaker[{self.name}]: Transitioning from {self.state} to CLOSED")
            self.failure_count = 0
            self.state = "CLOSED"

    def record_failure(self, error: Optional[Exception] = None):
        with self.lock:
            self.failure_count += 1
            now = time.time()
            if self.state == "HALF_OPEN" or self.failure_count >= self.failure_threshold:
                if self.state != "OPEN":
                    logger.warning(
                        f"CircuitBreaker[{self.name}]: Tripping to OPEN (failures={self.failure_count}, err={error}). Fast-failing for {self.recovery_timeout}s."
                    )
                self.state = "OPEN"
                self.last_state_change = now


vikunja_circuit_breaker = CircuitBreaker()

def ensure_auth():
    """Ensures VIKUNJA_API_TOKEN and TRAC_PASSWORD are set in environment, falling back to ~/.bashrc."""
    changed = False
    if not os.getenv("VIKUNJA_API_TOKEN") or not os.getenv("TRAC_PASSWORD"):
        bashrc_path = os.path.expanduser("~/.bashrc")
        if os.path.exists(bashrc_path):
            try:
                with open(bashrc_path, "r") as f:
                    for line in f:
                        if "export VIKUNJA_API_TOKEN=" in line and not os.getenv("VIKUNJA_API_TOKEN"):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            os.environ["VIKUNJA_API_TOKEN"] = val
                            logger.info("VIKUNJA_API_TOKEN found in ~/.bashrc.")
                            changed = True
                        if "export TRAC_PASSWORD=" in line and not os.getenv("TRAC_PASSWORD"):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            os.environ["TRAC_PASSWORD"] = val
                            logger.info("TRAC_PASSWORD found in ~/.bashrc.")
                            changed = True
            except Exception as e:
                logger.error(f"Error reading ~/.bashrc: {e}")
    
    if not os.getenv("VIKUNJA_API_TOKEN"):
        logger.warning("VIKUNJA_API_TOKEN not found.")
    if not os.getenv("TRAC_PASSWORD"):
        logger.warning("TRAC_PASSWORD not found.")

# Ensure auth is available
ensure_auth()


def _get_all_projects(host, token, include_filters=False):
    """
    Fetch all Vikunja projects, de-duplicated by id. The /projects endpoint can return the
    full set on every page request, so we dedupe and stop once a page adds nothing new.
    Saved filters appear here as pseudo-projects with negative ids; excluded by default
    (they cannot hold tasks).
    """
    import requests
    url = f"{host}/api/v1/projects"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    by_id = {}
    page = 1
    while page <= 50:  # hard safety cap
        resp = requests.get(url, headers=headers, params={"page": page})
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        added = 0
        for p in batch:
            pid = p.get("id")
            if pid not in by_id:
                by_id[pid] = p
                added += 1
        if added == 0 or len(batch) < 50:  # nothing new, or a short final page
            break
        page += 1
    projects = list(by_id.values())
    if not include_filters:
        projects = [p for p in projects if (p.get("id") or 0) > 0]
    return projects


def _resolve_project_id(project, host, token):
    """
    Resolve a project NAME (or numeric id) to an existing project_id.
    Match only - NEVER create. Returns (project_id, None) on success or (None, error_str).
    """
    # Numeric id passes through unchanged.
    try:
        return int(project), None
    except (ValueError, TypeError):
        pass

    name = str(project).strip().lower()
    projects = _get_all_projects(host, token)
    active = [p for p in projects if not p.get("is_archived")]

    exact = [p for p in active if str(p.get("title", "")).strip().lower() == name]
    if len(exact) == 1:
        return exact[0]["id"], None
    if len(exact) > 1:
        ids = ", ".join(f"{p['title']} (id {p['id']})" for p in exact)
        return None, f"Ambiguous project '{project}': multiple exact matches: {ids}"

    subs = [p for p in active if name in str(p.get("title", "")).strip().lower()]
    if len(subs) == 1:
        return subs[0]["id"], None

    catalog = ", ".join(sorted(str(p.get("title", "")) for p in active))
    if subs:
        cand = ", ".join(f"{p['title']} (id {p['id']})" for p in subs)
        return None, f"Ambiguous project '{project}'. Candidates: {cand}. All projects: {catalog}"
    return None, (f"No project named '{project}' exists. Projects are matched, never created. "
                  f"Existing projects: {catalog}")


def _html_desc_to_wiki(desc_html):
    """Convert a Vikunja task's rich-text HTML description into MoinMoin wiki markup."""
    if not desc_html:
        return ""
    text = desc_html
    text = re.sub(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', r'[[\1|\2]]', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'</p>\s*<p[^>]*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?p[^>]*>', '', text, flags=re.IGNORECASE)
    text = html.unescape(text)
    return text.strip()


# Valid Trac `component` values (per trac_get_ticket_fields). Vikunja project titles are
# matched against this set (case-insensitive), with a few common aliases, to auto-pick a
# component. If nothing matches confidently (e.g. project is "Inbox"), the caller is told
# so it can ask the user or override explicitly.
VALID_TRAC_COMPONENTS = {
    "board", "church", "eldercare", "finance", "food", "geeks", "healthcare",
    "maintenance", "persdev", "pops-kms", "recreation", "sysadmin",
}
COMPONENT_ALIASES = {
    "health": "healthcare", "medical": "healthcare",
    "sys admin": "sysadmin", "it": "sysadmin", "systems": "sysadmin",
    "personal development": "persdev", "kms": "pops-kms",
}


def _guess_component_for_project(project_id, host, token):
    """
    Returns (component_or_None, project_title, confident_bool).
    """
    try:
        projects = _get_all_projects(host, token)
    except Exception:
        return None, None, False
    proj = next((p for p in projects if p.get("id") == project_id), None)
    proj_title = (proj or {}).get("title", "")
    key = str(proj_title).strip().lower()
    if key in VALID_TRAC_COMPONENTS:
        return key, proj_title, True
    if key in COMPONENT_ALIASES:
        return COMPONENT_ALIASES[key], proj_title, True
    return None, proj_title, False


@mcp.tool(name="vikunja_ping")
def ping() -> str:
    """A simple ping tool to verify MCP transport connectivity."""
    logger.info("Vikunja: Ping")
    return "pong"

def format_description_for_vikunja(desc: Optional[str]) -> Optional[str]:
    """Converts Markdown description to HTML so Vikunja's TipTap editor renders clickable links."""
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

def _confirm_created_task(title: str, project_id: int, host: str, token: str, max_age_seconds: int = 180) -> Optional[dict]:
    """
    Reconciles whether a task was created on Vikunja following an unconfirmed/timed-out request.
    Prevents duplicate task creation on network/timeout errors (resolves #4198).
    """
    try:
        import requests
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        # 1. Check the newest tasks in the project (sorted descending by ID)
        url = f"{host}/api/v1/projects/{project_id}/tasks"
        params = {"sort_by[]": "id", "order_by[]": "desc", "per_page": 20}
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        if resp.ok:
            tasks = resp.json()
            now = datetime.datetime.now(datetime.timezone.utc)
            for t in tasks:
                if t.get("title", "").strip().lower() == title.strip().lower():
                    created_str = t.get("created")
                    if created_str:
                        try:
                            created_dt = datetime.datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                            age = (now - created_dt).total_seconds()
                            if age <= max_age_seconds:
                                return t
                        except Exception:
                            return t
                    else:
                        return t

        # 2. Fallback: query filter endpoint
        clean_search = re.sub(r'[\'"\\]', '', title).strip()
        if clean_search:
            filter_url = f"{host}/api/v1/tasks"
            filter_str = f"project_id = {project_id} && title ~ '{clean_search}'"
            filter_resp = requests.get(filter_url, headers=headers, params={"filter": filter_str}, timeout=10)
            if filter_resp.ok:
                for t in filter_resp.json():
                    if t.get("title", "").strip().lower() == title.strip().lower():
                        return t
    except Exception as e:
        logger.warning(f"Error checking task confirmation: {e}")
    return None

@mcp.tool(name="vikunja_create_task")
def create_task(title: str, description: str = "", project_id: int = 1, project: Optional[str] = None, labels: Optional[List[str]] = None, due_date: Optional[str] = None) -> str:
    """
    Create a new task in Vikunja.
    title: Task title (words starting with * are extracted as labels).
    description: Detailed description (Markdown supported). Put source links here in
        markdown so they are clickable, e.g. [subject](https://mail.google.com/mail/u/0/#all/<id>).
    project_id: Numeric ID of the project (Default: 1 - Inbox).
    project: Project NAME to match to an EXISTING project (e.g. 'maintenance', 'sysadmin').
        Matched case-insensitively; NEVER creates a project. If given, it overrides project_id.
        If no project matches, returns an error listing existing projects (it does not create one).
    labels: List of labels to attach.
    due_date: ISO format date (e.g., 2026-03-04T13:00:00).
    """
    logger.info(f"Vikunja: Create task '{title}' (project={project!r}, project_id={project_id})")
    try:
        if not vikunja_circuit_breaker.can_execute():
            return f"Error creating Vikunja task: Circuit breaker is OPEN (Vikunja host temporarily unreachable or failing). Try again shortly."

        token = os.getenv("VIKUNJA_API_TOKEN")
        host = os.getenv("VIKUNJA_URL", "http://todo.home.arpa").rstrip('/')

        # Resolve a project name to an existing project_id (match only, never create).
        if project is not None and str(project).strip() != "":
            resolved, err = _resolve_project_id(project, host, token)
            if err:
                return f"Error: {err}"
            project_id = resolved

        # Re-parse labels from title if provided
        words = title.split()
        title_labels = [w[1:] for w in words if w.startswith('*')]
        clean_title = ' '.join([w for w in words if not w.startswith('*')])

        all_labels = title_labels
        if labels:
            all_labels.extend(labels)

        html_description = format_description_for_vikunja(description)

        try:
            result = cvt.create_task(
                title=clean_title,
                description=html_description or "",
                project_id=project_id,
                is_favorite=True,
                host=host,
                token=token,
                labels=all_labels,
                due_date=due_date
            )
            task_id = result.get('id') if isinstance(result, dict) else None
            vikunja_circuit_breaker.record_success()
            if task_id:
                return f"Successfully created Vikunja task #{task_id}: {clean_title} (project_id={project_id})"
            return f"Successfully created Vikunja task: {clean_title} (project_id={project_id})"
        except Exception as e:
            # Check for timeout or transient network drop
            is_timeout = isinstance(e, (TimeoutError, urllib.error.URLError)) or "timeout" in str(e).lower() or "timed out" in str(e).lower()

            # Reconciliation check: did the task actually get created despite the timeout/drop?
            reconciled = _confirm_created_task(clean_title, project_id, host, token)
            if reconciled:
                task_id = reconciled.get('id')
                vikunja_circuit_breaker.record_success()
                logger.info(f"Reconciled created task #{task_id} ('{clean_title}') after exception: {e}")
                return f"Successfully created Vikunja task #{task_id}: {clean_title} (project_id={project_id}) [confirmed via reconciliation after transient timeout]"

            if is_timeout:
                logger.warning(f"Create task timed out for '{clean_title}'. Retrying once after backoff...")
                time.sleep(1.0)
                try:
                    result = cvt.create_task(
                        title=clean_title,
                        description=html_description or "",
                        project_id=project_id,
                        is_favorite=True,
                        host=host,
                        token=token,
                        labels=all_labels,
                        due_date=due_date
                    )
                    task_id = result.get('id') if isinstance(result, dict) else None
                    vikunja_circuit_breaker.record_success()
                    if task_id:
                        return f"Successfully created Vikunja task #{task_id}: {clean_title} (project_id={project_id}) [on retry]"
                    return f"Successfully created Vikunja task: {clean_title} (project_id={project_id}) [on retry]"
                except Exception as retry_err:
                    reconciled_after_retry = _confirm_created_task(clean_title, project_id, host, token)
                    if reconciled_after_retry:
                        task_id = reconciled_after_retry.get('id')
                        vikunja_circuit_breaker.record_success()
                        return f"Successfully created Vikunja task #{task_id}: {clean_title} (project_id={project_id}) [confirmed via reconciliation after retry timeout]"
                    vikunja_circuit_breaker.record_failure(retry_err)
                    logger.error(f"Error creating Vikunja task after retry: {retry_err}")
                    return f"Error creating Vikunja task after retry: {retry_err}"

            vikunja_circuit_breaker.record_failure(e)
            logger.error(f"Error creating Vikunja task: {e}")
            return f"Error creating Vikunja task: {e}"
    except Exception as e:
        logger.error(f"Error creating Vikunja task: {e}")
        return f"Error creating Vikunja task: {e}"

@mcp.tool(name="vikunja_get_task")
def get_task(task_id: int) -> str:
    """Fetch details of a Vikunja task by its ID."""
    logger.info(f"Vikunja: Get task {task_id}")
    try:
        if not vikunja_circuit_breaker.can_execute():
            return f"Error fetching Vikunja task: Circuit breaker is OPEN (Vikunja host temporarily unreachable or failing). Try again shortly."
        task = ctfv.get_vikunja_task(task_id)
        vikunja_circuit_breaker.record_success()
        return json.dumps(task, indent=2)
    except Exception as e:
        vikunja_circuit_breaker.record_failure(e)
        logger.error(f"Error fetching Vikunja task: {e}")
        return f"Error fetching Vikunja task {task_id}: {e}"

@mcp.tool(name="vikunja_update_task")
def update_task(task_id: int, title: Optional[str] = None, description: Optional[str] = None, labels: Optional[List[str]] = None, due_date: Optional[str] = None, is_favorite: Optional[bool] = None, done: Optional[bool] = None, priority: Optional[Union[int, str]] = None) -> str:
    """
    Update an existing Vikunja task.
    task_id: The ID of the task to update.
    title: Updated task title.
    description: Updated detailed description (Markdown supported).
    labels: List of labels to attach.
    due_date: ISO format date (e.g., 2026-03-04T13:00:00).
    is_favorite: Boolean to mark as favorite.
    done: Boolean to mark task as done or open.
    priority: Priority level as name ('now', 'urgent', 'high', 'medium', 'low', 'unset') or integer 0-5.
    """
    logger.info(f"Vikunja: Update task {task_id}")
    try:
        if not vikunja_circuit_breaker.can_execute():
            return f"Error updating Vikunja task: Circuit breaker is OPEN (Vikunja host temporarily unreachable or failing). Try again shortly."

        import requests
        token = os.getenv("VIKUNJA_API_TOKEN")
        host = os.getenv("VIKUNJA_URL", "http://todo.home.arpa").rstrip('/')
        
        task_url = f"{host}/api/v1/tasks/{task_id}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # Vikunja POST /tasks/{id} replaces omitted fields with zero-values.
        # Fetch existing task to preserve unmodified attributes across partial updates.
        get_resp = requests.get(task_url, headers=headers, timeout=15)
        get_resp.raise_for_status()
        existing = get_resp.json()

        payload = {
            "title": existing.get("title", ""),
            "description": existing.get("description", ""),
            "done": existing.get("done", False),
            "is_favorite": existing.get("is_favorite", False),
            "priority": existing.get("priority", 0),
        }
        if existing.get("labels"):
            payload["labels"] = existing.get("labels")
        if existing.get("due_date") and not existing["due_date"].startswith("0001-01-01"):
            payload["due_date"] = existing["due_date"]

        if title is not None:
            payload["title"] = title
        if description is not None:
            payload["description"] = format_description_for_vikunja(description)
        if due_date is not None:
            payload["due_date"] = due_date
        if is_favorite is not None:
            payload["is_favorite"] = is_favorite
        if done is not None:
            payload["done"] = done
        if priority is not None:
            if isinstance(priority, str) and not priority.isdigit():
                p_int = PRIORITY_MAP.get(priority.lower())
                if p_int is None:
                    return f"Unknown priority '{priority}'. Use: now, urgent, high, medium, low, unset, or 0-5."
                payload["priority"] = p_int
            else:
                payload["priority"] = int(priority)
            
        response = requests.post(task_url, headers=headers, json=payload, timeout=20)
        response.raise_for_status()
            
        if labels:
            resolved_labels = []
            existing_labels = cvt.get_all_labels(host, token)
            label_map = {l['title'].lower(): l for l in existing_labels}
            
            for label_name in labels:
                existing_lbl = label_map.get(label_name.lower())
                if existing_lbl:
                    resolved_labels.append({"id": existing_lbl['id'], "title": existing_lbl['title']})
                else:
                    new_label = cvt.create_label(host, token, label_name)
                    if new_label:
                        resolved_labels.append({"id": new_label['id'], "title": new_label['title']})
                        
            for label in resolved_labels:
                cvt.add_label_to_task(host, token, task_id, label['id'])
                
        vikunja_circuit_breaker.record_success()
        return f"Successfully updated Vikunja task {task_id}"
    except Exception as e:
        vikunja_circuit_breaker.record_failure(e)
        logger.error(f"Error updating Vikunja task: {e}")
        return f"Error updating Vikunja task {task_id}: {e}"

@mcp.tool(name="vikunja_create_trac_ticket")
def create_trac_ticket(task_id: int, component: Optional[str] = None, priority: str = "major", keywords: str = "awp, crdo, Jen") -> str:
    """
    Create a Trac ticket based on a Vikunja task and link them.
    task_id: The ID of the Vikunja task.
    component: Trac component (e.g., 'recreation', 'sysadmin'). If omitted, it is guessed
        from the task's Vikunja project name (matched against valid Trac components); if
        that guess isn't confident (e.g. project is "Inbox"), defaults to 'recreation' and
        the response flags this so the caller can confirm/correct with the user.
    priority: Trac priority.
    keywords: Comma-separated keywords.
    """
    logger.info(f"Vikunja: Create Trac ticket from task {task_id}")
    try:
        token = os.getenv("VIKUNJA_API_TOKEN")
        host = os.getenv("VIKUNJA_URL", "http://todo.home.arpa").rstrip('/')

        # 1. Fetch Vikunja Task
        task = ctfv.get_vikunja_task(task_id)
        summary = task.get('title')
        vikunja_desc = task.get('description', '')
        vikunja_link = f"http://todo.gafla.us.com/tasks/{task_id}"

        # 1a. Auto-pick a component from the task's Vikunja project if not given explicitly.
        component_note = ""
        if not component:
            guessed, proj_title, confident = _guess_component_for_project(task.get("project_id"), host, token)
            if guessed:
                component = guessed
            else:
                component = "recreation"
                component_note = (
                    f"\n\nNote: Vikunja project '{proj_title}' didn't map confidently to a "
                    f"Trac component, defaulted to 'recreation'. Valid components: "
                    f"{', '.join(sorted(VALID_TRAC_COMPONENTS))}."
                )

        # 1b. Build a properly cited wiki link back to the Vikunja task (title as link text,
        # WWOS-style citation), followed by the task description converted to wiki markup.
        today = datetime.date.today().isoformat()
        description = (
            f"'''[[{vikunja_link}|{summary}]]''' "
            f"<ref>Vikunja Task: [[{vikunja_link}|{summary}]] retrieved {today}</ref>"
        )
        wiki_desc = _html_desc_to_wiki(vikunja_desc)
        if wiki_desc:
            description += f"\n\n{wiki_desc}"

        # 2. Create XML Payload
        xml_payload = ctfv.create_trac_ticket_xml(summary, description, component, priority, keywords)

        # 3. Send to Trac
        response_xml = ctfv.send_to_trac(xml_payload)

        # 4. Parse Response
        if "<int>" in response_xml:
            ticket_id = response_xml.split("<int>")[1].split("</int>")[0]
            trac_public_url = f"{ctfv.TRAC_PUBLIC_URL_BASE}/{ticket_id}"

            # 5. Update Vikunja Task
            if trac_public_url not in vikunja_desc:
                new_desc = vikunja_desc
                if new_desc:
                    new_desc += "<br><br>"
                new_desc += f'<a href="{trac_public_url}">Trac Ticket #{ticket_id}: {summary}</a>'
                ctfv.update_vikunja_task(task_id, new_desc)

            return (
                f"Successfully created Trac Ticket #{ticket_id} (component={component}) "
                f"and linked to Vikunja Task {task_id}.{component_note}"
            )
        else:
            return f"Failed to create Trac ticket. Response: {response_xml}"

    except Exception as e:
        logger.error(f"Error creating Trac ticket from Vikunja task: {e}")
        return f"Error: {e}"

@mcp.tool(name="vikunja_list_labels")
def list_labels() -> str:
    """List all available labels in Vikunja."""
    logger.info("Vikunja: List labels")
    try:
        token = os.getenv("VIKUNJA_API_TOKEN")
        host = os.getenv("VIKUNJA_URL", "http://todo.home.arpa").rstrip('/')
        labels = cvt.get_all_labels(host, token)
        return json.dumps(labels, indent=2)
    except Exception as e:
        logger.error(f"Error listing labels: {e}")
        return f"Error listing labels: {e}"

@mcp.tool(name="vikunja_list_projects")
def list_projects() -> str:
    """
    List all Vikunja projects (id, title, parent_project_id, is_archived) so a domain name
    can be matched to a project_id. Projects are matched, NEVER created.
    """
    logger.info("Vikunja: List projects")
    try:
        token = os.getenv("VIKUNJA_API_TOKEN")
        host = os.getenv("VIKUNJA_URL", "http://todo.home.arpa").rstrip('/')
        projects = _get_all_projects(host, token)
        slim = [
            {
                "id": p.get("id"),
                "title": p.get("title"),
                "parent_project_id": p.get("parent_project_id"),
                "is_archived": p.get("is_archived"),
            }
            for p in projects
        ]
        return json.dumps(slim, indent=2)
    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        return f"Error listing projects: {e}"

def _resolve_labels_in_filter(filter_str: str, host: str, token: str) -> str:
    """
    Resolves human-readable label names to numeric label IDs in Vikunja filter strings.
    Handles:
      - labels = <name|id>
      - labels != <name|id>
      - labels in (<name1>, <name2>) / labels in <name1>, <name2>
      - labels not in (<name1>, <name2>) / labels not in <name1>, <name2>
      - Quoted names ('my label', "my label")
    """
    if not filter_str or "label" not in filter_str.lower():
        return filter_str

    try:
        existing_labels = cvt.get_all_labels(host, token)
        label_map = {}
        for l in existing_labels:
            key = l['title'].lower()
            if key not in label_map:
                label_map[key] = []
            label_map[key].append(str(l['id']))
    except Exception as e:
        logger.warning(f"Failed to fetch labels for filter resolution: {e}")
        return filter_str

    # 1. Handle "labels in (...)" or "labels in a, b" or "labels not in (...)"
    def _replace_in(match):
        field = match.group(1)
        op = match.group(2)
        raw_vals = match.group(3).strip().strip("()")
        parts = [p.strip() for p in raw_vals.split(",") if p.strip()]
        resolved_parts = []
        for p in parts:
            clean = p.strip().strip("'\"")
            if clean.isdigit() or (clean.startswith("-") and clean[1:].isdigit()):
                resolved_parts.append(clean)
            else:
                lbl_ids = label_map.get(clean.lower())
                if lbl_ids:
                    resolved_parts.extend(lbl_ids)
                else:
                    resolved_parts.append("0")
        return f"{field} {op} {', '.join(resolved_parts)}"

    in_pattern = re.compile(
        r'\b(labels?)\s+(in|not\s+in)\s*(\([^)]+\)|(?:\s*[\'"][^\'"]+[\'"]|\s*[^\s,()&|]+)(?:\s*,\s*(?:[\'"][^\'"]+[\'"]|[^\s,()&|]+))*)',
        re.IGNORECASE
    )
    filter_str = in_pattern.sub(_replace_in, filter_str)

    # 2. Handle "labels = val", "labels != val", "labels LIKE val", etc.
    def _replace_cmp(match):
        field = match.group(1) # labels
        op = match.group(2)    # = / != / LIKE / etc.
        raw_val = match.group(3)
        clean = raw_val.strip().strip("'\"")
        if clean.isdigit() or (clean.startswith("-") and clean[1:].isdigit()):
            return f"{field} {op} {clean}"
        lbl_ids = label_map.get(clean.lower())
        if lbl_ids:
            if len(lbl_ids) == 1:
                return f"{field} {op} {lbl_ids[0]}"
            elif op == "=":
                return f"{field} in {', '.join(lbl_ids)}"
            elif op == "!=":
                return f"{field} not in {', '.join(lbl_ids)}"
            return f"{field} {op} {lbl_ids[0]}"
        logger.warning(f"Label '{clean}' not found in Vikunja during filter resolution; mapping to 0")
        return f"{field} {op} 0"

    cmp_pattern = re.compile(
        r'\b(labels?)\s*(=|!=|~|like)\s*(\'(?:[^\'\\]|\\.)*\'|"(?:[^"\\]|\\.)*"|[^\s&|()]+)',
        re.IGNORECASE
    )
    filter_str = cmp_pattern.sub(_replace_cmp, filter_str)

    # Normalize singular 'label ' to 'labels '
    filter_str = re.sub(r'\blabel\s+(=|!=|~|like|in|not\s+in)', r'labels \1', filter_str, flags=re.IGNORECASE)

    return filter_str

@mcp.tool(name="vikunja_search_tasks")
def search_tasks(filter: str = "done = false") -> str:
    """
    Search for tasks in Vikunja using a filter string.
    Label names in filters (e.g., 'labels = awp') are automatically resolved to numeric IDs.
    Example filters:
    - 'done = false'
    - 'assignees = will && done = false'
    - 'labels = awp && done = false'
    - 'labels in (awp, connie) && done = false'
    - 'title ~ some_keyword'
    """
    logger.info(f"Vikunja: Search tasks with filter '{filter}'")
    try:
        if not vikunja_circuit_breaker.can_execute():
            return f"Error searching tasks: Circuit breaker is OPEN (Vikunja host temporarily unreachable or failing). Try again shortly."

        import requests
        token = os.getenv("VIKUNJA_API_TOKEN")
        host = os.getenv("VIKUNJA_URL", "http://todo.home.arpa").rstrip('/')
        
        resolved_filter = _resolve_labels_in_filter(filter, host, token)
        if resolved_filter != filter:
            logger.info(f"Vikunja: Filter resolved from '{filter}' to '{resolved_filter}'")

        # Use the specific endpoint for tasks with filter
        url = f"{host}/api/v1/tasks"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        params = {"filter": resolved_filter}
        
        response = requests.get(url, headers=headers, params=params, timeout=20)
        if not response.ok:
            error_body = response.text
            try:
                err_json = response.json()
                if "message" in err_json:
                    error_body = f"{err_json.get('message')} (code {err_json.get('code')})"
            except Exception:
                pass
            vikunja_circuit_breaker.record_failure()
            return f"Error searching tasks (HTTP {response.status_code}): {error_body}"

        tasks = response.json()
        vikunja_circuit_breaker.record_success()
        return json.dumps(tasks, indent=2)
    except Exception as e:
        vikunja_circuit_breaker.record_failure(e)
        logger.error(f"Error searching tasks: {e}")
        return f"Error searching tasks: {e}"

PRIORITY_MAP = {
    "unset": 0, "none": 0,
    "low": 1,
    "medium": 2,
    "high": 3,
    "urgent": 4,
    "now": 5,
}

@mcp.tool(name="vikunja_get_tasks_by_priority")
def get_tasks_by_priority(priority: str = "now", include_done: bool = True) -> str:
    """
    Fetch all tasks at a given priority level, open and/or closed.
    priority: Name ('now', 'urgent', 'high', 'medium', 'low', 'unset', 'starred') or integer 0-5.
    include_done: If True (default), return both open and closed tasks.
    Returns a compact summary table.
    """
    logger.info(f"Vikunja: Get tasks by priority='{priority}' include_done={include_done}")
    try:
        if not vikunja_circuit_breaker.can_execute():
            return f"Error fetching tasks by priority: Circuit breaker is OPEN (Vikunja host temporarily unreachable or failing). Try again shortly."

        import requests

        is_starred = False
        # Resolve priority to int or starred flag
        if isinstance(priority, str) and priority.lower() in ("star", "starred", "favorite"):
            is_starred = True
            priority_int = -1
        elif isinstance(priority, str) and not priority.isdigit():
            priority_int = PRIORITY_MAP.get(priority.lower())
            if priority_int is None:
                return f"Unknown priority '{priority}'. Use: now, urgent, high, medium, low, unset, starred, or 0-5."
        else:
            priority_int = int(priority)

        token = os.getenv("VIKUNJA_API_TOKEN")
        host = os.getenv("VIKUNJA_URL", "http://todo.home.arpa").rstrip('/')
        url = f"{host}/api/v1/tasks"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        tasks = []
        page = 1
        max_pages = 100

        if is_starred:
            params = {}
            if not include_done:
                params["filter"] = "done = false"
            while page <= max_pages:
                params["page"] = page
                response = requests.get(url, headers=headers, params=params, timeout=20)
                response.raise_for_status()
                batch = response.json()
                if not batch:
                    break
                tasks.extend([t for t in batch if t.get("is_favorite")])
                total_pages = int(response.headers.get("x-pagination-total-pages", 1))
                if page >= total_pages:
                    break
                page += 1
        else:
            filter_str = f"priority = {priority_int}"
            if not include_done:
                filter_str += " && done = false"
            while page <= max_pages:
                params = {"filter": filter_str, "page": page}
                response = requests.get(url, headers=headers, params=params, timeout=20)
                response.raise_for_status()
                batch = response.json()
                if not batch:
                    break
                tasks.extend(batch)
                total_pages = int(response.headers.get("x-pagination-total-pages", 1))
                if page >= total_pages:
                    break
                page += 1

        vikunja_circuit_breaker.record_success()
        label = "STARRED" if is_starred else next((k for k, v in PRIORITY_MAP.items() if v == priority_int), str(priority_int))

        if not tasks:
            return f"No tasks found with priority '{label}'."

        open_tasks = [t for t in tasks if not t.get("done")]
        done_tasks = [t for t in tasks if t.get("done")]

        lines = [f"Priority: {label.upper()} — {len(tasks)} task(s) ({len(open_tasks)} open, {len(done_tasks)} done)\n"]
        for t in sorted(tasks, key=lambda x: (x.get("done", False), x.get("id"))):
            status = "✓" if t.get("done") else "○"
            due = t.get("due_date", "")[:10] if t.get("due_date") else ""
            due_str = f" [due {due}]" if due and due != "0001-01-01" else ""
            lines.append(f"  {status} [{t['id']}] {t['title']}{due_str}")

        return "\n".join(lines)
    except Exception as e:
        vikunja_circuit_breaker.record_failure(e)
        logger.error(f"Error fetching tasks by priority: {e}")
        return f"Error fetching tasks by priority: {e}"


if __name__ == "__main__":
    logger.info("Starting Vikunja MCP server...")
    mcp.run()
