#!/usr/bin/env python3
"""
================================================================================
Filename:       trac.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-11
Context:        http://trac.home.arpa/ticket/3585

Purpose:
    Trac XML-RPC service layer for the Pops KMS REST API. Creates Trac tickets
    via XML-RPC using HTTP Basic authentication. Converts Markdown descriptions
    to MoinMoin wiki syntax via lib.trac_formatter (reused from
    /home/will/ansible-netbox/scripts/lib/trac_formatter.py) and sanitizes
    ticket text to prevent accidental secret leakage.

    NOTE on module-level side effects in create_trac_ticket.py:
    Importing that script directly is unsafe because at module scope it:
      - calls exit(1) if TRAC_PASSWORD is not set
      - embeds the cleartext password in the module-level TRAC_URL string
      - appends unconditionally to sys.path
    get_trac_password() is therefore replicated here rather than imported, and
    lib.trac_formatter is imported directly by adding the scripts directory to
    sys.path ourselves.

Secrets:
    TRAC_PASSWORD (env var, ~/.bashrc fallback) - Trac XML-RPC auth for user
                  will (overridable via TRAC_USER env var). Value is never
                  logged, printed, or included in any returned data or error
                  message.

Usage:
    from app.services.trac import create_trac_ticket
    result = create_trac_ticket(
        summary="Fix the thing",
        description="**Details here.**",
        component="pops-kms",
        priority="minor",
    )
    # result: {"ticket_id": 1234, "url": "http://trac.gafla.us.com/ticket/1234"}

Revision History:
    1.0 - Initial implementation (Phase 2 subtask P2.2). Trac #3585.
================================================================================
"""

import os
import sys
import xmlrpc.client

# ---------------------------------------------------------------------------
# Reuse trac_formatter from the shared scripts lib. We add the scripts
# directory to sys.path rather than importing create_trac_ticket (which has
# fatal module-level side effects documented in the header above).
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = "/home/will/ansible-netbox/scripts"
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from lib.trac_formatter import markdown_to_moinmoin, sanitize_content  # noqa: E402


class TracError(Exception):
    """
    Raised when Trac XML-RPC communication fails.

    The message is intentionally safe for HTTP response bodies - it never
    contains the password or any other credential.
    """


def _get_trac_password() -> str | None:
    """
    Read TRAC_PASSWORD from the environment, falling back to ~/.bashrc.

    Replicates get_trac_password() from create_trac_ticket.py without the
    module-level exit() side effect present in that script.

    Returns:
        The password string, or None if it cannot be found.
    """
    password = os.getenv("TRAC_PASSWORD")
    if password:
        return password

    bashrc_path = os.path.expanduser("~/.bashrc")
    if os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    if "export TRAC_PASSWORD=" in line:
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            return parts[1].strip().strip('"').strip("'")
        except Exception:
            pass
    return None


def create_trac_ticket(
    summary: str,
    description: str,
    component: str = "pops-kms",
    priority: str = "minor",
    keywords: str = "",
    cc: str = "will",
    ticket_type: str = "task",
    markdown: bool = True,
) -> dict:
    """
    Create a Trac ticket via XML-RPC and return its id and public URL.

    Args:
        summary:     One-line ticket title (must be non-empty; caller validates).
        description: Ticket body text; converted from Markdown when markdown=True.
        component:   Trac component (default: "pops-kms").
        priority:    Trac priority string (default: "minor").
        keywords:    Keyword string; commas are normalised to spaces (default: "").
        cc:          Comma-separated CC user list (default: "will").
        ticket_type: Trac ticket type field (default: "task").
        markdown:    When True, convert description from Markdown to MoinMoin
                     before submitting (default: True).

    Returns:
        dict with keys:
            ticket_id  (int)  - newly created Trac ticket number
            url        (str)  - public-facing URL for the ticket

    Raises:
        TracError: on missing credentials, XML-RPC faults, or network errors.
                   The exception message is safe to relay to HTTP clients.
    """
    password = _get_trac_password()
    if not password:
        raise TracError(
            "Trac credentials not configured - set TRAC_PASSWORD env var"
        )

    trac_user = os.getenv("TRAC_USER", "will")
    trac_host = os.getenv("TRAC_HOST", "trac.home.arpa")
    trac_path = os.getenv("TRAC_PATH", "/login/xmlrpc")
    # Password is interpolated into the URL only within this local scope
    # and is never returned or logged.
    trac_url = f"http://{trac_user}:{password}@{trac_host}{trac_path}"

    # Convert and sanitize description
    processed = description
    if markdown:
        processed = markdown_to_moinmoin(processed)
    processed = sanitize_content(processed)

    # Normalise keywords to space-separated (Trac convention)
    processed_keywords = keywords.replace(",", " ")

    attributes = {
        "component": component,
        "keywords": processed_keywords,
        "type": ticket_type,
        "priority": priority,
        "cc": cc,
    }

    try:
        server = xmlrpc.client.ServerProxy(trac_url)
        ticket_id = server.ticket.create(summary, processed, attributes, True)
    except xmlrpc.client.Fault as exc:
        raise TracError(
            f"Trac XML-RPC fault {exc.faultCode}: {exc.faultString}"
        ) from exc
    except Exception as exc:
        # Do not include trac_url in the message - it contains the password.
        raise TracError(
            f"Failed to connect to Trac server: {type(exc).__name__}"
        ) from exc

    return {
        "ticket_id": int(ticket_id),
        "url": f"http://trac.gafla.us.com/ticket/{ticket_id}",
    }
