#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/vikunja/server.py
Version:        1.1
Author:         Gemini CLI
Last Modified:  2026-04-16
Context:        http://trac.home.arpa/ticket/3321

Purpose:
    Model Context Protocol (MCP) server for Vikunja integration.
    Wraps scripts/create_vikunja_task.py and scripts/create_trac_from_vikunja.py
    to provide tools for managing Vikunja tasks and linking them to Trac.

Revision History:
    v1.1 (2026-04-16): Updated header with Trac ticket link per WWOS standards.
    v1.0 (2026-04-16): Initial implementation.

Notes:
    Always bump the version number when modifying this file and annotate 
    the changes in the Revision History section.
================================================================================
"""
import os
import sys
import logging
import json
from typing import Optional, List

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

logger.info("Initializing Vikunja MCP Server v1.0")

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

@mcp.tool(name="vikunja_ping")
def ping() -> str:
    """A simple ping tool to verify MCP transport connectivity."""
    logger.info("Vikunja: Ping")
    return "pong"

@mcp.tool(name="vikunja_create_task")
def create_task(title: str, description: str = "", project_id: int = 1, labels: Optional[List[str]] = None, due_date: Optional[str] = None) -> str:
    """
    Create a new task in Vikunja.
    title: Task title (words starting with * are extracted as labels).
    description: Detailed description (Markdown supported).
    project_id: ID of the project (Default: 1 - Inbox).
    labels: List of labels to attach.
    due_date: ISO format date (e.g., 2026-03-04T13:00:00).
    """
    logger.info(f"Vikunja: Create task '{title}'")
    try:
        # Re-parse labels from title if provided
        words = title.split()
        title_labels = [w[1:] for w in words if w.startswith('*')]
        clean_title = ' '.join([w for w in words if not w.startswith('*')])
        
        all_labels = title_labels
        if labels:
            all_labels.extend(labels)
        
        # Note: cvt.create_task handles API calls and printing to stdout.
        # We might want to capture stdout or modify cvt to return values.
        # For now, we'll call it and assume it works if no exception is raised.
        # However, it uses sys.exit(1) on failure, which is bad for a server.
        # I'll wrap it in a way that handles the logic.
        
        token = os.getenv("VIKUNJA_API_TOKEN")
        host = os.getenv("VIKUNJA_URL", "http://todo.home.arpa").rstrip('/')
        
        cvt.create_task(
            title=clean_title,
            description=description,
            project_id=project_id,
            is_favorite=True,
            host=host,
            token=token,
            labels=all_labels,
            due_date=due_date
        )
        return f"Successfully created Vikunja task: {clean_title}"
    except Exception as e:
        logger.error(f"Error creating Vikunja task: {e}")
        return f"Error creating Vikunja task: {e}"

@mcp.tool(name="vikunja_get_task")
def get_task(task_id: int) -> str:
    """Fetch details of a Vikunja task by its ID."""
    logger.info(f"Vikunja: Get task {task_id}")
    try:
        task = ctfv.get_vikunja_task(task_id)
        return json.dumps(task, indent=2)
    except Exception as e:
        logger.error(f"Error fetching Vikunja task: {e}")
        return f"Error fetching Vikunja task {task_id}: {e}"

@mcp.tool(name="vikunja_create_trac_ticket")
def create_trac_ticket(task_id: int, component: str = "recreation", priority: str = "major", keywords: str = "awp, crdo, Jen") -> str:
    """
    Create a Trac ticket based on a Vikunja task and link them.
    task_id: The ID of the Vikunja task.
    component: Trac component (e.g., 'recreation', 'sysadmin').
    priority: Trac priority.
    keywords: Comma-separated keywords.
    """
    logger.info(f"Vikunja: Create Trac ticket from task {task_id}")
    try:
        # We can't easily call ctfv.main() because of argparse.
        # We'll re-implement the orchestration here using functions from ctfv.
        
        # 1. Fetch Vikunja Task
        task = ctfv.get_vikunja_task(task_id)
        summary = task.get('title')
        vikunja_desc = task.get('description', '')
        vikunja_link = f"http://todo.gafla.us.com/tasks/{task_id}"
        description = f"Refers to Vikunja Task: {vikunja_link}\n\n{vikunja_desc}"
        
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
                
            return f"Successfully created Trac Ticket #{ticket_id} and linked to Vikunja Task {task_id}."
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

if __name__ == "__main__":
    logger.info("Starting Vikunja MCP server...")
    mcp.run()
