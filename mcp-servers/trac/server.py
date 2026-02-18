import os
import xmlrpc.client
import logging
from typing import Optional
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("trac-server")

def get_trac_password():
    """Gets the TRAC_PASSWORD, falling back to ~/.bashrc if not set in environment."""
    password = os.getenv("TRAC_PASSWORD")
    if password:
        return password

    bashrc_path = os.path.expanduser("~/.bashrc")
    if os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "r") as f:
                for line in f:
                    if "export TRAC_PASSWORD=" in line:
                        # Extract value: export TRAC_PASSWORD="value" or export TRAC_PASSWORD=value
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip('"').strip("'")
                            return val
        except Exception:
            pass
    return None

# Trac Configuration
TRAC_URL = "http://trac.home.arpa/login/xmlrpc"
TRAC_USER = "gemini"
TRAC_PASSWORD = get_trac_password()

if not TRAC_PASSWORD:
    logging.warning("TRAC_PASSWORD environment variable is not set (and not in ~/.bashrc). Operations may fail.")

def get_proxy():
    """Create and return an XML-RPC proxy."""
    if not TRAC_PASSWORD:
        raise ValueError("TRAC_PASSWORD is not set")
    
    # Construct URL with auth
    # Format: http://user:password@host/path
    auth_url = TRAC_URL.replace("http://", f"http://{TRAC_USER}:{TRAC_PASSWORD}@", 1)
    return xmlrpc.client.ServerProxy(auth_url)

@mcp.tool()
def get_ticket(ticket_id: int) -> str:
    """
    Fetch details of a Trac ticket by its ID.
    Returns a formatted string with ticket summary, description, and attributes.
    """
    try:
        proxy = get_proxy()
        ticket = proxy.ticket.get(ticket_id)
        # ticket is [id, time_created, time_changed, attributes]
        t_id, created, changed, attrs = ticket
        
        output = [f"Ticket: #{t_id}"]
        output.append(f"Summary: {attrs.get('summary', 'No summary')}")
        output.append(f"Status: {attrs.get('status', 'Unknown')}")
        output.append(f"Priority: {attrs.get('priority', 'Unknown')}")
        output.append(f"Keywords: {attrs.get('keywords', '')}")
        output.append("-" * 20)
        output.append(f"Description:\n{attrs.get('description', '')}")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error fetching ticket #{ticket_id}: {str(e)}"

@mcp.tool()
def update_ticket(ticket_id: int, comment: str, keywords: Optional[str] = None, status: Optional[str] = None) -> str:
    """
    Update a Trac ticket with a comment and optional attributes.
    
    Args:
        ticket_id: The ID of the ticket to update.
        comment: The comment text to add.
        keywords: Optional new keywords (overwrites existing if provided).
        status: Optional new status (e.g., 'closed', 'reopened').
    """
    try:
        proxy = get_proxy()
        attributes = {}
        if keywords:
            attributes['keywords'] = keywords
        if status:
            attributes['status'] = status
            if status == 'closed':
                attributes['resolution'] = 'fixed' # Default to fixed if closing
        
        # update(id, comment, attributes, notify=True)
        # We assume author is handled by the auth user 'gemini'
        proxy.ticket.update(ticket_id, comment, attributes, True)
        return f"Successfully updated ticket #{ticket_id}."
    except Exception as e:
        return f"Error updating ticket #{ticket_id}: {str(e)}"

@mcp.tool()
def create_ticket(summary: str, description: str, type: str = "task", priority: str = "major", keywords: str = "") -> str:
    """
    Create a new Trac ticket.
    
    Args:
        summary: The title of the ticket.
        description: The body of the ticket.
        type: Ticket type (task, bug, enhancement). Defaults to 'task'.
        priority: Priority (blocker, critical, major, minor, trivial). Defaults to 'major'.
        keywords: Comma-separated keywords.
    """
    try:
        proxy = get_proxy()
        attributes = {
            'type': type,
            'priority': priority,
            'keywords': keywords,
            'cc': 'will' # Standard practice to cc user
        }
        
        # create(summary, description, attributes, notify=True)
        ticket_id = proxy.ticket.create(summary, description, attributes, True)
        return f"Successfully created ticket #{ticket_id}."
    except Exception as e:
        return f"Error creating ticket: {str(e)}"

@mcp.tool()
def search_tickets(query: str) -> str:
    """
    Search for tickets using Trac query syntax.
    Example query: 'status=!closed&keywords=~ynh2'
    """
    try:
        proxy = get_proxy()
        # query(qstr) returns list of ticket IDs
        ticket_ids = proxy.ticket.query(query)
        
        if not ticket_ids:
            return "No tickets found matching query."
            
        results = []
        for t_id in ticket_ids[:10]: # Limit to 10 results
            try:
                # get(id) -> [id, time_created, time_changed, attributes]
                t_info = proxy.ticket.get(t_id)
                attrs = t_info[3]
                results.append(f"#{t_id}: {attrs.get('summary')} ({attrs.get('status')})")
            except:
                results.append(f"#{t_id}: (Error fetching details)")
                
        return "\n".join(results)
    except Exception as e:
        return f"Error searching tickets: {str(e)}"

if __name__ == "__main__":
    mcp.run()
