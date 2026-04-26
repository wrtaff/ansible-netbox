#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/wwos/server.py
Version:        1.4
Author:         Gemini CLI
Last Modified:  2026-04-25
Context:        WWOS (MediaWiki) Integration

Purpose:
    Model Context Protocol (MCP) server for WWOS MediaWiki integration.
    Wraps scripts/create_wwos_page.py and other WWOS scripts to provide
    tools for fetching, creating, and updating wiki pages.

Revision History:
    v1.4 (2026-04-25): Fix _read_bashrc_password() to handle $'...' ANSI C quoting —
                       previously returned $'<password>!!' instead of <password> causing
                       both ensure_auth() validation attempts to fail.
    v1.3 (2026-04-25): Harden ensure_auth(): validate env var against live login when
                       it differs from ~/.bashrc value; replace with .bashrc value if
                       env var fails auth. Prevents silent breakage from corrupted env
                       vars (e.g., bash !! history expansion).
    v1.2 (2026-04-25): Fix auth race: move ensure_auth() before script imports so
                       WWOS_PASSWORD is set in os.environ before any module captures
                       it at import time (update_wwos_page.py reads PASSWORD at module
                       level). Logging setup also moved before script imports.
    v1.1 (2026-04-10): Added wwos_generate_citation and wwos_import_from_wikipedia tools.
    v1.0 (2026-04-10): Initial implementation wrapping existing WWOS scripts.

Notes:
    Always bump the version number when modifying this file and annotate
    the changes in the Revision History section.
================================================================================
"""
import os
import sys
import logging
import re
import subprocess
import requests as _requests
from typing import Optional, List

# Add project root to path to allow importing from scripts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Configure logging early so ensure_auth() can log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/wwos_mcp.log',
    filemode='a'
)
logger = logging.getLogger("wwos-mcp")

def _read_bashrc_password():
    """Read WWOS_PASSWORD from ~/.bashrc, return None if not found."""
    bashrc_path = os.path.expanduser("~/.bashrc")
    if not os.path.exists(bashrc_path):
        return None
    try:
        with open(bashrc_path, "r") as f:
            for line in f:
                if "export WWOS_PASSWORD=" in line:
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        val = parts[1].strip()
                        # Handle $'...' ANSI C quoting (immune to !! expansion)
                        m = re.match(r"^\$'(.+)'$", val)
                        if m:
                            return m.group(1)
                        return val.strip('"').strip("'")
    except Exception as e:
        logger.error(f"Error reading ~/.bashrc: {e}")
    return None


def _try_auth(password):
    """Attempt a MediaWiki login; return True on success, False otherwise."""
    api_url = "http://wwos.home.arpa/api.php"
    try:
        session = _requests.Session()
        resp = session.get(api_url, params={
            "action": "query", "meta": "tokens", "type": "login", "format": "json"
        }, timeout=5)
        token = resp.json()["query"]["tokens"]["logintoken"]
        login = session.post(api_url, data={
            "action": "login", "lgname": "will", "lgpassword": password,
            "lgtoken": token, "format": "json"
        }, timeout=5)
        return login.json().get("login", {}).get("result") == "Success"
    except Exception as e:
        logger.warning(f"Auth validation request failed: {e}")
        return False


def ensure_auth():
    """Ensures WWOS_PASSWORD is set and valid in the environment.

    Strategy:
    - If the env var is missing: read from ~/.bashrc unconditionally.
    - If the env var is present but differs from ~/.bashrc: validate both via a
      live login attempt and promote whichever succeeds. This catches the case
      where the env var was corrupted (e.g., by bash !! history expansion).
    - If both sources agree, skip the HTTP round-trip.
    """
    env_pw = os.getenv("WWOS_PASSWORD")
    bashrc_pw = _read_bashrc_password()

    if not env_pw:
        if bashrc_pw:
            os.environ["WWOS_PASSWORD"] = bashrc_pw
            logger.info("WWOS_PASSWORD not in environment; set from ~/.bashrc.")
        else:
            logger.warning("WWOS_PASSWORD not found in environment or ~/.bashrc.")
        return

    # Env var is set; if it matches .bashrc (or .bashrc is absent) trust it.
    if not bashrc_pw or env_pw == bashrc_pw:
        logger.info("WWOS_PASSWORD is set in environment.")
        return

    # Mismatch between env var and .bashrc — validate to pick the correct one.
    logger.warning("WWOS_PASSWORD env var differs from ~/.bashrc value; validating both.")
    if _try_auth(env_pw):
        logger.info("Environment WWOS_PASSWORD validated successfully.")
    elif _try_auth(bashrc_pw):
        logger.warning("Environment WWOS_PASSWORD failed auth; replacing with ~/.bashrc value.")
        os.environ["WWOS_PASSWORD"] = bashrc_pw
    else:
        logger.error("Both WWOS_PASSWORD values failed validation (server may be unreachable); keeping env var.")

# Ensure WWOS_PASSWORD is in os.environ BEFORE importing scripts — several
# scripts (notably update_wwos_page.py) read os.getenv("WWOS_PASSWORD") at
# module level, so the env var must be present before the import statements run.
ensure_auth()

from mcp.server.fastmcp import FastMCP
from scripts import create_wwos_page as cwp
from scripts import update_wwos_page as uwp
from scripts import get_wwos_category_members as gcm
from scripts import list_all_wwos_categories as lac
from scripts import get_wwos_category_info as gci
from scripts import wwos_citation as wc
from scripts import wikipedia_to_wwos as wtw

# Initialize FastMCP server
mcp = FastMCP("wwos-server")

logger.info("Initializing WWOS MCP Server v1.4")

@mcp.tool(name="wwos_ping")
def ping() -> str:
    """A simple ping tool to verify MCP transport connectivity."""
    logger.info("WWOS: Ping")
    return "pong"

@mcp.tool(name="wwos_get_page")
def get_page(page_name: str) -> str:
    """Fetch the raw wikitext content of a WWOS page."""
    logger.info(f"WWOS: Get page '{page_name}'")
    try:
        content = cwp.get_page_content(page_name)
        if content is None:
            return f"Page '{page_name}' not found."
        return content
    except Exception as e:
        logger.error(f"Error fetching page: {e}")
        return f"Error fetching page '{page_name}': {e}"

@mcp.tool(name="wwos_create_page")
def create_page(page_name: str, categories: str, content: str, summary: str = "Page created by AI assistant") -> str:
    """
    Create a new page on WWOS.
    categories: Comma-separated list (e.g., 'SysAdmin, Automation')
    """
    logger.info(f"WWOS: Create page '{page_name}'")
    try:
        success = cwp.create_wwos_page(
            page_name=page_name,
            categories=categories,
            summary=summary,
            content_body=content
        )
        return f"Successfully created page '{page_name}'." if success else f"Failed to create page '{page_name}'."
    except Exception as e:
        logger.error(f"Error creating page: {e}")
        return f"Error creating page '{page_name}': {e}"

@mcp.tool(name="wwos_update_page")
def update_page(page_name: str, content: str, summary: str = "Page updated by AI assistant") -> str:
    """Update an existing page on WWOS with full content."""
    logger.info(f"WWOS: Update page '{page_name}'")
    try:
        # update_wwos_page(page_id=None, page_name=None, full_content=None, categories=None, summary="...")
        success = uwp.update_wwos_page(
            page_name=page_name,
            full_content=content,
            summary=summary
        )
        return f"Successfully updated page '{page_name}'." if success else f"Failed to update page '{page_name}'."
    except Exception as e:
        logger.error(f"Error updating page: {e}")
        return f"Error updating page '{page_name}': {e}"

@mcp.tool(name="wwos_list_categories")
def list_categories() -> str:
    """List all categories available on the WWOS MediaWiki."""
    logger.info("WWOS: List all categories")
    try:
        all_cats = []
        current = None
        while True:
            cats = lac.get_categories(current)
            if not cats or (len(cats) == 1 and cats[0] == current):
                break
            all_cats.extend(cats)
            current = cats[-1]
            if len(cats) < 500:
                break
        
        unique_cats = sorted(list(set(all_cats)))
        return "\n".join(unique_cats)
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        return f"Error listing categories: {e}"

@mcp.tool(name="wwos_get_category_members")
def get_category_members(category_name: str) -> str:
    """List all pages belonging to a specific category."""
    logger.info(f"WWOS: Get members of category '{category_name}'")
    try:
        members = gcm.get_category_members(category_name)
        if not members:
            return f"No members found for category '{category_name}'."
        return "\n".join(members)
    except Exception as e:
        logger.error(f"Error getting category members: {e}")
        return f"Error getting category members for '{category_name}': {e}"

@mcp.tool(name="wwos_get_category_info")
def get_category_info(category_name: str) -> str:
    """Fetch the content/description of a specific Category page."""
    logger.info(f"WWOS: Get info for category '{category_name}'")
    try:
        content = gci.get_category_info(category_name)
        if content is None:
            return f"Category '{category_name}' not found."
        return content
    except Exception as e:
        logger.error(f"Error fetching category info: {e}")
        return f"Error fetching category info for '{category_name}': {e}"

@mcp.tool(name="wwos_generate_citation")
def generate_citation(url: str, title: Optional[str] = None, source: Optional[str] = None, ref_only: bool = False) -> str:
    """
    Generate a WWOS-style citation.
    Standard format: [URL TITLE] <ref>SOURCE: [URL TITLE] retrieved YYYY-MM-DD</ref>
    """
    logger.info(f"WWOS: Generate citation for {url}")
    return wc.format_wwos_citation(url, title, source, ref_only)

@mcp.tool(name="wwos_import_from_wikipedia")
def import_from_wikipedia(url: str, categories: str, title: Optional[str] = None) -> str:
    """
    Scrape a Wikipedia article and create a new page on WWOS.
    url: Wikipedia article URL.
    categories: Comma-separated WWOS categories.
    title: Optional override for the WWOS page title.
    """
    logger.info(f"WWOS: Import from Wikipedia {url}")
    try:
        # Check if page exists first
        final_title = title if title else url.split("/wiki/")[-1].replace("_", " ")
        if cwp.page_exists(final_title):
            return f"Error: Page '{final_title}' already exists on WWOS."

        # Fetch Wikipedia content
        real_title, raw_content, wik_categories, canonical_url = wtw.get_wikipedia_content(url)
        target_title = title if title else real_title
        
        # Format for WWOS
        formatted_content = wtw.format_content(raw_content, canonical_url, real_title)
        
        # Combine categories
        user_cats = {cat.strip() for cat in categories.split(",") if cat.strip()}
        all_cats = user_cats.union(set(wik_categories))
        combined_cats = ", ".join(all_cats)
        
        # Create page
        success = cwp.create_wwos_page(
            page_name=target_title,
            categories=combined_cats,
            summary=f"Imported from {url}",
            content_body=formatted_content
        )
        
        return f"Successfully imported '{target_title}' from Wikipedia." if success else f"Failed to import from Wikipedia."
    except Exception as e:
        logger.error(f"Error importing from Wikipedia: {e}")
        return f"Error importing from Wikipedia: {e}"

if __name__ == "__main__":
    logger.info("Starting WWOS MCP server...")
    mcp.run()
