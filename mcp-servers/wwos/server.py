#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/wwos/server.py
Version:        1.1
Author:         Gemini CLI
Last Modified:  2026-04-10
Context:        WWOS (MediaWiki) Integration

Purpose:
    Model Context Protocol (MCP) server for WWOS MediaWiki integration.
    Wraps scripts/create_wwos_page.py and other WWOS scripts to provide
    tools for fetching, creating, and updating wiki pages.

Revision History:
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
from typing import Optional, List

# Add project root to path to allow importing from scripts
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from mcp.server.fastmcp import FastMCP
from scripts import create_wwos_page as cwp
from scripts import update_wwos_page as uwp
from scripts import get_wwos_category_members as gcm
from scripts import list_all_wwos_categories as lac
from scripts import get_wwos_category_info as gci
from scripts import wwos_citation as wc
from scripts import wikipedia_to_wwos as wtw

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/wwos_mcp.log',
    filemode='a'
)
logger = logging.getLogger("wwos-mcp")

# Initialize FastMCP server
mcp = FastMCP("wwos-server")

logger.info("Initializing WWOS MCP Server v1.1")

def ensure_auth():
    """Ensures WWOS_PASSWORD is set in environment, falling back to ~/.bashrc."""
    if not os.getenv("WWOS_PASSWORD"):
        bashrc_path = os.path.expanduser("~/.bashrc")
        if os.path.exists(bashrc_path):
            try:
                with open(bashrc_path, "r") as f:
                    for line in f:
                        if "export WWOS_PASSWORD=" in line:
                            parts = line.split("=", 1)
                            if len(parts) == 2:
                                val = parts[1].strip().strip('"').strip("'")
                                os.environ["WWOS_PASSWORD"] = val
                                logger.info("WWOS_PASSWORD found in ~/.bashrc and set to environment.")
                                return
            except Exception as e:
                logger.error(f"Error reading ~/.bashrc: {e}")
        logger.warning("WWOS_PASSWORD not found in environment or ~/.bashrc.")

# Ensure auth is available for all tools
ensure_auth()

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
