#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/trac/server.py
Version:        1.7
Author:         Gemini CLI
Last Modified:  2026-02-27
Context:        http://trac.home.arpa/ticket/2933

Purpose:
    Model Context Protocol (MCP) server for Trac integration.
    Provides tools for ticket management (get, update, create, search)
    directly within AI agent sessions.

Revision History:
    v1.7 (2026-02-27): Added priority validation and support for updating priority.
    v1.6 (2026-02-24): Added ticket comments to get_ticket, URL-encoded password,
                       and added resolution/author/action to update_ticket.
    v1.5 (2026-02-21): Enforced space-separated keywords and component validation.
    v1.4 (2026-02-18): Verified tool stability and finalized 'trac_' prefix naming.
    v1.3 (2026-02-18): Fixed duplicate tool definitions and standardized names.
    v1.2 (2026-02-18): Added file-based logging to /tmp/trac_mcp.log and ping tool.
    v1.1 (2026-02-18): Changed default user to 'will' and added author='gemini'.
    v1.0 (2026-02-18): Initial implementation with stdio transport.
================================================================================
"""
import os
import xmlrpc.client
import logging
from typing import Optional
from urllib.parse import quote
from mcp.server.fastmcp import FastMCP

# Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/trac_mcp.log',
    filemode='a'
)
logger = logging.getLogger("trac-mcp")

# Initialize FastMCP server
mcp = FastMCP("trac-server")

def get_trac_password():
    """Gets the TRAC_PASSWORD, falling back to ~/.bashrc if not set in environment."""
    password = os.getenv("TRAC_PASSWORD")
    if password:
        logger.info("TRAC_PASSWORD found in environment.")
        return password

    bashrc_path = os.path.expanduser("~/.bashrc")
    if os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "r") as f:
                for line in f:
                    if "export TRAC_PASSWORD=" in line:
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip('"').strip("'")
                            logger.info("TRAC_PASSWORD found in ~/.bashrc.")
                            return val
        except Exception as e:
            logger.error(f"Error reading ~/.bashrc: {e}")
    
    logger.warning("TRAC_PASSWORD not found.")
    return None

# Trac Configuration
TRAC_URL = "http://trac.home.arpa/login/xmlrpc"
TRAC_USER = os.getenv("TRAC_USER", "will")
TRAC_PASSWORD = get_trac_password()

logger.info(f"Initialized Trac MCP v1.6 with user: {TRAC_USER}")

def get_proxy():
    """Create and return an XML-RPC proxy."""
    if not TRAC_PASSWORD:
        logger.error("Attempted to get proxy without TRAC_PASSWORD.")
        raise ValueError("TRAC_PASSWORD is not set")
    
    # Construct URL with auth, URL-encoding the password for special characters
    encoded_password = quote(TRAC_PASSWORD, safe='')
    auth_url = TRAC_URL.replace("http://", f"http://{TRAC_USER}:{encoded_password}@", 1)
    return xmlrpc.client.ServerProxy(auth_url)

@mcp.tool(name="trac_ping")
def ping() -> str:
    """A simple ping tool to verify MCP transport connectivity without external dependencies."""
    logger.info("Ping tool called.")
    return "pong"

@mcp.tool(name="trac_get_ticket")
def get_ticket(ticket_id: int) -> str:
    """
    Fetch details of a Trac ticket by its ID.
    Returns a formatted string with ticket summary, description, and comments.
    """
    logger.info(f"Fetching ticket #{ticket_id}")
    try:
        proxy = get_proxy()
        ticket = proxy.ticket.get(ticket_id)
        # ticket is [id, time_created, time_changed, attributes]
        t_id, created, changed, attrs = ticket
        
        output = [f"Ticket: #{t_id}"]
        output.append(f"Summary: {str(attrs.get('summary', 'No summary'))}")
        output.append(f"Status: {str(attrs.get('status', 'Unknown'))}")
        output.append(f"Priority: {str(attrs.get('priority', 'Unknown'))}")
        output.append(f"Keywords: {str(attrs.get('keywords', ''))}")
        output.append("-" * 20)
        output.append(f"Description:\n{str(attrs.get('description', ''))}")
        
        # Add comments from changelog
        try:
            changelog = proxy.ticket.changeLog(ticket_id)
            comments = []
            for change in changelog:
                # change is [time, author, field, old_value, new_value, permanent]
                t, author, field, old, new, perm = change
                if field == 'comment' and new:
                    comments.append(f"\n[{author}] ({t}):\n{new}")
            
            if comments:
                output.append("-" * 20)
                output.append("History/Comments:")
                output.extend(comments)
        except Exception as ce:
            logger.warning(f"Could not fetch comments for ticket #{ticket_id}: {ce}")

        logger.info(f"Successfully fetched ticket #{ticket_id}")
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Error fetching ticket #{ticket_id}: {str(e)}")
        return f"Error fetching ticket #{ticket_id}: {str(e)}"

@mcp.tool(name="trac_update_ticket")
def update_ticket(ticket_id: int, comment: str, component: Optional[str] = None, keywords: Optional[str] = None, status: Optional[str] = None, resolution: Optional[str] = None, author: str = "gemini", action: Optional[str] = None, priority: Optional[str] = None) -> str:
    """
    Update a Trac ticket with a comment and optional attributes.
    
    Args:
        ticket_id: The ID of the ticket to update.
        comment: The comment text to add.
        component: Optional new component (must exist).
        keywords: Optional new keywords (space-separated, overwrites existing if provided).
        status: Optional new status (e.g., 'closed', 'reopened').
        resolution: Optional resolution (e.g., 'fixed', 'invalid', 'periodic hold').
        author: The author name to use for the update. Defaults to 'gemini'.
        action: The workflow action to perform (e.g., 'resolve').
        priority: Optional new priority (must exist).
    """
    logger.info(f"Updating ticket #{ticket_id}")
    try:
        proxy = get_proxy()
        attributes = {}
        if keywords:
            # Enforce space-separated keywords
            attributes['keywords'] = ' '.join(keywords.replace(',', ' ').split())
        if component:
            # Validate component
            valid_components = proxy.ticket.component.getAll()
            if component not in valid_components:
                logger.warning(f"Invalid component provided: {component}")
                return f"Error: Invalid component '{component}'. Valid components are: {', '.join(valid_components)}"
            attributes['component'] = component
        if priority:
            # Validate priority
            valid_priorities = proxy.ticket.priority.getAll()
            if priority not in valid_priorities:
                logger.warning(f"Invalid priority provided: {priority}")
                return f"Error: Invalid priority '{priority}'. Valid priorities are: {', '.join(valid_priorities)}"
            attributes['priority'] = priority
        if status:
            attributes['status'] = status
        if resolution:
            attributes['resolution'] = resolution
        if action:
            attributes['action'] = action
            if action == 'resolve' and resolution:
                attributes['action_resolve_resolve_as'] = resolution
        elif status == 'closed' and not resolution:
            attributes['resolution'] = 'fixed' # Default to fixed if closing without resolution
        
        # update(id, comment, attributes, notify=True, author=author)
        proxy.ticket.update(ticket_id, comment, attributes, True, author)
        logger.info(f"Successfully updated ticket #{ticket_id}")
        return f"Successfully updated ticket #{ticket_id}."
    except Exception as e:
        logger.error(f"Error updating ticket #{ticket_id}: {str(e)}")
        return f"Error updating ticket #{ticket_id}: {str(e)}"

@mcp.tool(name="trac_create_ticket")
def create_ticket(summary: str, description: str, component: str, type: str = "task", priority: str = "major", keywords: str = "") -> str:
    """
    Create a new Trac ticket.
    
    Args:
        summary: The title of the ticket.
        description: The body of the ticket.
        component: The Trac component. MUST be an existing component.
        type: Ticket type (task, bug, enhancement). Defaults to 'task'.
        priority: Priority (blocker, critical, major, minor, trivial). Defaults to 'major'.
        keywords: Space-separated keywords.
    """
    logger.info(f"Creating new ticket: {summary}")
    try:
        proxy = get_proxy()
        
        # Enforce space-separated keywords
        keywords = ' '.join(keywords.replace(',', ' ').split())
        
        # Validate component
        valid_components = proxy.ticket.component.getAll()
        if component not in valid_components:
            logger.warning(f"Invalid component provided: {component}")
            return f"Error: Invalid component '{component}'. Valid components are: {', '.join(valid_components)}"

        # Validate priority
        valid_priorities = proxy.ticket.priority.getAll()
        if priority not in valid_priorities:
            logger.warning(f"Invalid priority provided: {priority}")
            return f"Error: Invalid priority '{priority}'. Valid priorities are: {', '.join(valid_priorities)}"

        attributes = {
            'type': str(type),
            'priority': str(priority),
            'keywords': str(keywords),
            'component': str(component),
            'cc': 'will' # Standard practice to cc user
        }
        
        # create(summary, description, attributes, notify=True)
        ticket_id = proxy.ticket.create(summary, description, attributes, True)
        logger.info(f"Successfully created ticket #{ticket_id}")
        return f"Successfully created ticket #{ticket_id}."
    except Exception as e:
        logger.error(f"Error creating ticket: {str(e)}")
        return f"Error creating ticket: {str(e)}"

@mcp.tool(name="trac_search_tickets")
def search_tickets(query: str) -> str:
    """
    Search for tickets using Trac query syntax.
    Example query: 'status=!closed&keywords=~ynh2'
    """
    logger.info(f"Searching tickets with query: {query}")
    try:
        proxy = get_proxy()
        # query(qstr) returns list of ticket IDs
        ticket_ids = proxy.ticket.query(query)
        
        if not ticket_ids:
            logger.info("No tickets found matching query.")
            return "No tickets found matching query."
            
        results = []
        for t_id in ticket_ids[:10]: # Limit to 10 results
            try:
                # get(id) -> [id, time_created, time_changed, attributes]
                t_info = proxy.ticket.get(t_id)
                attrs = t_info[3]
                results.append(f"#{t_id}: {str(attrs.get('summary'))} ({str(attrs.get('status'))})")
            except Exception as e:
                logger.warning(f"Error fetching details for ticket #{t_id} in search: {e}")
                results.append(f"#{t_id}: (Error fetching details)")
        
        logger.info(f"Found {len(results)} results for query: {query}")
        return "\n".join(results)
    except Exception as e:
        logger.error(f"Error searching tickets: {str(e)}")
        return f"Error searching tickets: {str(e)}"

if __name__ == "__main__":
    logger.info("Starting Trac MCP server...")
    mcp.run()
