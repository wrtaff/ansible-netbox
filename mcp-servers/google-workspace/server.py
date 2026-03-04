#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/google-workspace/server.py
Version:        1.1
Author:         Gemini CLI
Last Modified:  2026-03-04
Context:        http://trac.home.arpa/ticket/3119

Purpose:
    Model Context Protocol (MCP) server for Google Workspace integration.
    Wraps scripts/google_workspace_manager.py to provide tools for Gmail,
    Google Drive, Calendar, and Tasks within AI agent sessions.

Revision History:
    v1.1 (2026-03-04): Updated header to WWOS standards; prepared for GitHub push.
    v1.0 (2026-02-26): Initial prototype wrapping google_workspace_manager.py.

Notes:
    Always bump the version number when modifying this file and annotate 
    the changes in the Revision History section.
================================================================================
"""
import os
import sys
import logging
from typing import Optional

# Add project root to path to allow importing from scripts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP
from scripts import google_workspace_manager as gwm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/google_workspace_mcp.log',
    filemode='a'
)
logger = logging.getLogger("google-workspace-mcp")

# Initialize FastMCP server
mcp = FastMCP("google-workspace-server")

logger.info("Initializing Google Workspace MCP Server v1.0")

# --- GMAIL TOOLS ---

@mcp.tool(name="gmail_list_messages")
def list_messages(query: str = "", max_results: int = 10) -> str:
    """List Gmail messages matching an optional query."""
    logger.info(f"Gmail: List messages with query='{query}'")
    # Redirect output to capture it
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.gmail_list_messages(query=query, max_results=max_results, output_format='json')
    return f.getvalue()

@mcp.tool(name="gmail_get_message")
def get_message(message_id: str) -> str:
    """Get full details of a Gmail message by its ID."""
    logger.info(f"Gmail: Get message {message_id}")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.gmail_get_message(message_id=message_id, output_format='json')
    return f.getvalue()

@mcp.tool(name="gmail_send_message")
def send_message(to: str, subject: str, body: str, attachment_path: Optional[str] = None) -> str:
    """Send an email message, optionally with an attachment."""
    logger.info(f"Gmail: Sending message to {to}")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.gmail_send_message(to=to, subject=subject, body=body, attachment_path=attachment_path, output_format='json')
    return f.getvalue()

@mcp.tool(name="gmail_create_draft")
def create_draft(to: str, subject: str, body: str, attachment_path: Optional[str] = None) -> str:
    """Create a draft email, optionally with an attachment."""
    logger.info(f"Gmail: Creating draft for {to}")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.gmail_create_draft(to=to, subject=subject, body=body, attachment_path=attachment_path, output_format='json')
    return f.getvalue()

# --- DRIVE TOOLS ---

@mcp.tool(name="drive_search")
def search_drive(query: Optional[str] = None, max_results: int = 10) -> str:
    """Search for files in Google Drive."""
    logger.info(f"Drive: Searching with query='{query}'")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.drive_search(query=query, max_results=max_results, output_format='json')
    return f.getvalue()

@mcp.tool(name="drive_download")
def download_drive_file(file_id: str, output_path: str) -> str:
    """Download a file from Google Drive to a local path."""
    logger.info(f"Drive: Downloading file {file_id} to {output_path}")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.drive_download_file(file_id=file_id, output_path=output_path, output_format='json')
    return f.getvalue()

@mcp.tool(name="drive_upload")
def upload_drive_file(file_path: str, mime_type: Optional[str] = None) -> str:
    """Upload a local file to Google Drive."""
    logger.info(f"Drive: Uploading {file_path}")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.drive_upload_file(file_path=file_path, mimetype=mime_type, output_format='json')
    return f.getvalue()

# --- CALENDAR TOOLS ---

@mcp.tool(name="calendar_list_events")
def list_calendar_events(max_results: int = 10) -> str:
    """List upcoming events from the primary calendar."""
    logger.info("Calendar: Listing events")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.calendar_list_events(max_results=max_results, output_format='json')
    return f.getvalue()

@mcp.tool(name="calendar_create_event")
def create_calendar_event(summary: str, start_time: str, duration_mins: int = 60, description: Optional[str] = None, attendees: Optional[str] = None) -> str:
    """Create a calendar event (start_time in ISO format)."""
    logger.info(f"Calendar: Creating event '{summary}' at {start_time}")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.calendar_create_event(summary=summary, start_time_str=start_time, duration_mins=duration_mins, description=description, attendees=attendees, output_format='json')
    return f.getvalue()

# --- TASKS TOOLS ---

@mcp.tool(name="tasks_list")
def list_tasks(max_results: int = 10) -> str:
    """List tasks from the default task list."""
    logger.info("Tasks: Listing tasks")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.tasks_list_tasks(max_results=max_results, output_format='json')
    return f.getvalue()

@mcp.tool(name="tasks_create")
def create_task(title: str, notes: Optional[str] = None, due_date: Optional[str] = None) -> str:
    """Create a new task."""
    logger.info(f"Tasks: Creating task '{title}'")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        gwm.tasks_create_task(title=title, notes=notes, due_date_str=due_date, output_format='json')
    return f.getvalue()

if __name__ == "__main__":
    logger.info("Starting Google Workspace MCP server...")
    mcp.run()
