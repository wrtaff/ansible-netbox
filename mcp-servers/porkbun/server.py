#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/porkbun/server.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-03-11
Context:        http://trac.gafla.us.com/ticket/3169

Purpose:
    Model Context Protocol (MCP) server for Porkbun DNS integration.
    Wraps scripts/porkbun_manager.py to provide tools for managing 
    DNS records within AI agent sessions.

Revision History:
    v1.0 (2026-03-11): Initial prototype wrapping porkbun_manager.py.

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
from scripts import porkbun_manager as pbm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/porkbun_mcp.log',
    filemode='a'
)
logger = logging.getLogger("porkbun-mcp")

# Initialize FastMCP server
mcp = FastMCP("porkbun-server")

logger.info("Initializing Porkbun MCP Server v1.0")

@mcp.tool(name="porkbun_list_records")
def list_records(domain: str) -> str:
    """List all DNS records for a given domain on Porkbun."""
    logger.info(f"Porkbun: Listing records for {domain}")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        pbm.list_records(domain, output_format='json')
    return f.getvalue()

@mcp.tool(name="porkbun_create_record")
def create_record(domain: str, type: str, name: str, content: str, ttl: int = 600, prio: Optional[str] = None) -> str:
    """Create a new DNS record on Porkbun (e.g., A, CNAME, MX)."""
    logger.info(f"Porkbun: Creating {type} record for {name}.{domain}")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        pbm.create_record(domain, type.upper(), name, content, ttl, prio)
    return f.getvalue()

@mcp.tool(name="porkbun_delete_record")
def delete_record(domain: str, record_id: str) -> str:
    """Delete a DNS record on Porkbun by its ID."""
    logger.info(f"Porkbun: Deleting record {record_id} from {domain}")
    import io
    from contextlib import redirect_stdout
    f = io.StringIO()
    with redirect_stdout(f):
        pbm.delete_record(domain, record_id)
    return f.getvalue()

if __name__ == "__main__":
    logger.info("Starting Porkbun MCP server...")
    mcp.run()
