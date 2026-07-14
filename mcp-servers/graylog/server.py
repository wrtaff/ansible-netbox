#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/graylog/server.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-07-14
Context:        http://trac.gafla.us.com/ticket/3439

Purpose:
    Model Context Protocol (MCP) server for Graylog integration.
    Wraps scripts/graylog_query.py to let agents pull the last N hours/days
    of log entries without hand-rolling the REST query every time, and to
    surface recurring patterns (candidate problems/fixes) via normalization.

Revision History:
    v1.0 (2026-07-14): Initial implementation wrapping graylog_query.py.

Notes:
    Always bump the version number when modifying this file and annotate
    the changes in the Revision History section.
================================================================================
"""
import os
import re
import sys
import collections
import logging
from typing import Optional, List, Dict, Any

# Add project root to path to allow importing from scripts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP
from scripts import graylog_query as gq

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/graylog_mcp.log',
    filemode='a'
)
logger = logging.getLogger("graylog-mcp")

# Initialize FastMCP server
mcp = FastMCP("graylog-server")

logger.info("Initializing Graylog MCP Server v1.0")


def _normalize(message: str) -> str:
    """Collapse variable substrings (IPs, ports, PIDs, hex, audit IDs) so
    repeated occurrences of the same underlying event group together."""
    m = re.sub(r'\b\d{1,3}(\.\d{1,3}){3}\b', '<IP>', message)
    m = re.sub(r'port \d+', 'port <N>', m)
    m = re.sub(r'\[\d+\]', '[<PID>]', m)
    m = re.sub(r'pid=\d+', 'pid=<PID>', m)
    m = re.sub(r'\b[0-9a-f]{8,}\b', '<HEX>', m, flags=re.I)
    m = re.sub(r'audit\(\d+\.\d+:\d+\)', 'audit(<TIMESTAMP>:<ID>)', m)
    return m.strip()


@mcp.tool(name="graylog_ping")
def ping() -> str:
    """Test connectivity and authentication to the Graylog server."""
    try:
        ok = gq.test_connection()
        return "Connected to Graylog" if ok else "Ping failed: see /tmp/graylog_mcp.log"
    except Exception as e:
        logger.error(f"Ping failed: {e}")
        return f"Ping failed: {str(e)}"


@mcp.tool(name="graylog_query")
def query(search: str = "*", hours: int = 24, limit: int = 500) -> List[Dict[str, Any]]:
    """
    Run a Graylog query and return matching messages.

    Args:
        search: Graylog query string (e.g. "source:router AND level:3"). Default "*" (all).
        hours:  Look-back window in hours. For a day-based window, pass days*24.
        limit:  Max messages to return (paginated internally, capped at Graylog's 500/page).
    """
    try:
        return gq.query_messages(search, hours=hours, limit=limit)
    except Exception as e:
        logger.error(f"Query failed for '{search}': {e}")
        return [{"error": str(e)}]


@mcp.tool(name="graylog_recent")
def recent(hours: int = 1, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Fetch the most recent messages across all sources (shorthand for query="*").

    Args:
        hours: Look-back window in hours. For a day-based window, pass days*24.
        limit: Max messages to return.
    """
    try:
        return gq.query_messages("*", hours=hours, limit=limit)
    except Exception as e:
        logger.error(f"Recent fetch failed: {e}")
        return [{"error": str(e)}]


@mcp.tool(name="graylog_summarize")
def summarize(search: str = "*", hours: int = 24, limit: int = 2000, top_n: int = 30) -> List[Dict[str, Any]]:
    """
    Fetch messages for a window and group them into recurring patterns, ranked
    by frequency. Use this instead of graylog_query when the goal is to spot
    problems or verify a fix landed (a pattern's count dropping to zero after
    a change, a new pattern appearing) rather than to read raw messages.

    Args:
        search: Graylog query string. Default "*" (all sources).
        hours:  Look-back window in hours. For a day-based window, pass days*24.
        limit:  Max raw messages to pull before grouping (higher = more accurate counts).
        top_n:  Number of top patterns to return.

    Returns:
        List of {count, source, example, pattern} sorted by count descending.
    """
    try:
        messages = gq.query_messages(search, hours=hours, limit=limit)
    except Exception as e:
        logger.error(f"Summarize query failed for '{search}': {e}")
        return [{"error": str(e)}]

    counts: collections.Counter = collections.Counter()
    examples: Dict[str, Dict[str, str]] = {}

    for m in messages:
        raw = m.get("message", "")
        pattern = _normalize(raw)
        counts[pattern] += 1
        examples[pattern] = {"source": m.get("source", ""), "message": raw, "timestamp": m.get("timestamp", "")}

    results = []
    for pattern, count in counts.most_common(top_n):
        ex = examples[pattern]
        results.append({
            "count": count,
            "source": ex["source"],
            "example": ex["message"][:300],
            "last_seen": ex["timestamp"],
            "pattern": pattern[:300],
        })
    return results


if __name__ == "__main__":
    logger.info("Starting Graylog MCP server...")
    mcp.run()
