#!/usr/bin/env python3
"""
================================================================================
Filename:       vikunja.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-11
Context:        http://trac.home.arpa/ticket/3585

Purpose:
    Vikunja task-creation service for the Pops KMS REST API. Wraps the
    create_vikunja_task.py library script (v1.5) located at
    /home/will/ansible-netbox/scripts by inserting that directory onto sys.path
    at import time. The script's create_task(), get_all_labels(), create_label(),
    and add_label_to_task() functions are reused directly; no logic is
    duplicated here.

    sys.path insertion note: /home/will/ansible-netbox/scripts is prepended
    inside this module (see _SCRIPTS_DIR block below) so the import is
    self-contained and does not require changes to PYTHONPATH or the venv.

Secrets:
    VIKUNJA_API_TOKEN  (env var; ~/.bashrc fallback resolved by _resolve_token()
                        and passed explicitly to create_task()) - Vikunja REST
                        API bearer-auth token. Value is never logged or included
                        in exception messages surfaced to callers.

Usage:
    from app.services.vikunja import create_vikunja_task, VikunjaError
    result = create_vikunja_task(title="My task", description="Details")
    # result keys: task_id (int), url (str), title (str)

Revision History:
    1.0 - Initial implementation (Phase 2 subtask P2.1). Trac #3585.
================================================================================
"""

import os
import sys

# ---------------------------------------------------------------------------
# Inject the scripts directory so create_vikunja_task.py can be imported as a
# library without modifying the script or the venv. Prepend so it takes
# precedence over any same-named module elsewhere on the path.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = "/home/will/ansible-netbox/scripts"
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import create_vikunja_task as _cvt  # noqa: E402 - must follow sys.path insertion

# Default Vikunja base URL used for constructing returned task URLs.
# The API calls use the same host so internal resolution stays consistent.
_VIKUNJA_HOST = "http://todo.home.arpa"
_VIKUNJA_EXTERNAL_HOST = "http://todo.gafla.us.com"

# Default project ID: 1 = Inbox (matches create_vikunja_task.py default).
_DEFAULT_PROJECT_ID = 1


class VikunjaError(Exception):
    """Raised when the Vikunja backend is unreachable or returns an error."""


def _resolve_token() -> str | None:
    """
    Return VIKUNJA_API_TOKEN from the environment, falling back to a line
    scan of ~/.bashrc for 'export VIKUNJA_API_TOKEN=...' if the variable is
    not already set. Returns None if the token cannot be found.
    """
    token = os.environ.get("VIKUNJA_API_TOKEN")
    if token:
        return token

    bashrc = os.path.expanduser("~/.bashrc")
    try:
        with open(bashrc, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("export VIKUNJA_API_TOKEN="):
                    val = stripped.split("=", 1)[1].strip().strip("'\"")
                    if val:
                        return val
    except OSError:
        pass

    return None


def create_vikunja_task(
    title: str,
    description: str = "",
    project_id: int | None = None,
    labels: list[str] | None = None,
    due: str | None = None,
) -> dict:
    """
    Create a Vikunja task by delegating to create_vikunja_task.create_task().

    Args:
        title:       Task title (must be non-empty; caller validates).
        description: Optional Markdown description.
        project_id:  Vikunja project ID. Defaults to 1 (Inbox) when None.
        labels:      List of label name strings. New labels are created
                     automatically by the underlying script.
        due:         ISO 8601 due-date string, e.g. "2026-03-04T13:00:00".

    Returns:
        dict with keys:
            task_id  (int)  - Vikunja task ID
            url      (str)  - Task URL on http://todo.gafla.us.com
            title    (str)  - Task title as stored by Vikunja

    Raises:
        VikunjaError: Token not configured, or the Vikunja backend returned
                      an error. The raw token value is never included in the
                      exception message.
    """
    effective_project_id = project_id if project_id is not None else _DEFAULT_PROJECT_ID
    effective_labels = list(labels) if labels else []

    token = _resolve_token()
    if not token:
        raise VikunjaError("VIKUNJA_API_TOKEN is not set and could not be read from ~/.bashrc")

    try:
        result = _cvt.create_task(
            title=title,
            description=description,
            project_id=effective_project_id,
            is_favorite=True,
            host=_VIKUNJA_HOST,
            token=token,
            labels=effective_labels,
            due_date=due,
        )
    except SystemExit:
        # create_task (v1.5) retains a sys.exit(1) guard for missing token;
        # we pre-check above so this path should not be reached, but handle
        # it defensively to prevent killing the API server process.
        raise VikunjaError("Vikunja API token not accepted by the script")
    except Exception as exc:
        raise VikunjaError(str(exc)) from exc

    task_id = result.get("id")
    task_url = f"{_VIKUNJA_EXTERNAL_HOST}/tasks/{task_id}"
    return {
        "task_id": task_id,
        "url": task_url,
        "title": result.get("title", title),
    }
