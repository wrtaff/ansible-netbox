#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/paperless/server.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-07-19
Purpose:
    Model Context Protocol (MCP) server for Paperless-ngx integration.
    Provides tools for document search, retrieval, upload, and management
    directly within AI agent sessions. (Trac #3955)
================================================================================
"""
import os
import logging
import json
import requests
from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/paperless_mcp.log',
    filemode='a'
)
logger = logging.getLogger("paperless-mcp")

# Paperless-ngx Configuration
PAPERLESS_URL = "http://paperless-ngx.home.arpa"
CONTENT_TRUNCATE = 8000
SNIPPET_LENGTH = 200

def get_paperless_token():
    """Gets the PAPERLESS_API_TOKEN, falling back to ~/.bashrc if not set in environment."""
    token = os.getenv("PAPERLESS_API_TOKEN")
    if token:
        logger.info("PAPERLESS_API_TOKEN found in environment.")
        return token

    bashrc_path = os.path.expanduser("~/.bashrc")
    if os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "r") as f:
                for line in f:
                    if "export PAPERLESS_API_TOKEN=" in line:
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip('"').strip("'")
                            logger.info("PAPERLESS_API_TOKEN found in ~/.bashrc.")
                            return val
        except Exception as e:
            logger.error(f"Error reading ~/.bashrc: {e}")

    logger.warning("PAPERLESS_API_TOKEN not found.")
    return None

PAPERLESS_TOKEN = get_paperless_token()

# Initialize FastMCP server
mcp = FastMCP("paperless-server")

def get_headers() -> Dict[str, str]:
    """Return auth headers for the Paperless-ngx API."""
    if not PAPERLESS_TOKEN:
        logger.error("Attempted to use Paperless without PAPERLESS_API_TOKEN.")
        raise ValueError("PAPERLESS_API_TOKEN is not set")
    return {"Authorization": f"Token {PAPERLESS_TOKEN}"}

def summarize_document(doc: Dict[str, Any], snippet: bool = True) -> Dict[str, Any]:
    """Reduce a full document record to a compact summary."""
    result = {
        "id": doc.get("id"),
        "title": doc.get("title"),
        "created": doc.get("created"),
        "correspondent": doc.get("correspondent"),
        "tags": doc.get("tags"),
    }
    if snippet:
        content = doc.get("content") or ""
        result["snippet"] = content[:SNIPPET_LENGTH].strip()
    return result

@mcp.tool(name="paperless_ping")
def ping() -> str:
    """Test connectivity to Paperless-ngx and report the API version if available."""
    try:
        resp = requests.get(f"{PAPERLESS_URL}/api/", headers=get_headers(), timeout=10)
        resp.raise_for_status()
        version = resp.headers.get("X-Version") or resp.headers.get("X-Api-Version")
        if version:
            return f"Connected to Paperless-ngx (version {version})"
        return "Connected to Paperless-ngx"
    except Exception as e:
        logger.error(f"Ping failed: {e}")
        return f"Ping failed: {str(e)}"

@mcp.tool(name="paperless_search_documents")
def search_documents(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Full-text search for documents. Returns id, title, created, correspondent, tags, and a content snippet per hit."""
    try:
        resp = requests.get(
            f"{PAPERLESS_URL}/api/documents/",
            headers=get_headers(),
            params={"query": query, "page_size": limit},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = [summarize_document(doc) for doc in data.get("results", [])[:limit]]
        logger.info(f"Search '{query}' returned {data.get('count')} hits, showing {len(results)}.")
        return results
    except Exception as e:
        logger.error(f"Search failed for '{query}': {e}")
        return [{"error": str(e)}]

@mcp.tool(name="paperless_get_document")
def get_document(document_id: int, include_content: bool = True) -> Dict[str, Any]:
    """Retrieve a document's metadata and (optionally) its OCR-extracted content by document ID. Content is truncated to ~8000 chars."""
    try:
        resp = requests.get(
            f"{PAPERLESS_URL}/api/documents/{document_id}/",
            headers=get_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        doc = resp.json()
        result = {
            "id": doc.get("id"),
            "title": doc.get("title"),
            "created": doc.get("created"),
            "added": doc.get("added"),
            "correspondent": doc.get("correspondent"),
            "document_type": doc.get("document_type"),
            "tags": doc.get("tags"),
            "original_file_name": doc.get("original_file_name"),
            "archive_serial_number": doc.get("archive_serial_number"),
        }
        if include_content:
            content = doc.get("content") or ""
            if len(content) > CONTENT_TRUNCATE:
                result["content"] = content[:CONTENT_TRUNCATE]
                result["content_note"] = (
                    f"Content truncated to {CONTENT_TRUNCATE} of {len(content)} chars."
                )
            else:
                result["content"] = content
        return result
    except Exception as e:
        logger.error(f"Failed to get document {document_id}: {e}")
        return {"error": str(e)}

@mcp.tool(name="paperless_list_recent")
def list_recent(limit: int = 5) -> List[Dict[str, Any]]:
    """List the most recently created documents (newest first)."""
    try:
        resp = requests.get(
            f"{PAPERLESS_URL}/api/documents/",
            headers=get_headers(),
            params={"ordering": "-created", "page_size": limit},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return [summarize_document(doc) for doc in data.get("results", [])[:limit]]
    except Exception as e:
        logger.error(f"Failed to list recent documents: {e}")
        return [{"error": str(e)}]

@mcp.tool(name="paperless_upload_document")
def upload_document(file_path: str, title: Optional[str] = None) -> Dict[str, Any]:
    """Upload a local file to Paperless-ngx for OCR processing. Returns the async task id; the document appears after processing."""
    try:
        path = os.path.expanduser(file_path)
        if not os.path.isfile(path):
            return {"error": f"File not found: {path}"}
        data = {}
        if title:
            data["title"] = title
        with open(path, "rb") as f:
            resp = requests.post(
                f"{PAPERLESS_URL}/api/documents/post_document/",
                headers=get_headers(),
                files={"document": (os.path.basename(path), f)},
                data=data,
                timeout=120,
            )
        resp.raise_for_status()
        task_id = resp.text.strip().strip('"')
        logger.info(f"Uploaded '{path}' as task {task_id}.")
        return {"task_id": task_id, "note": "Processing is asynchronous; document appears after OCR completes."}
    except Exception as e:
        logger.error(f"Failed to upload '{file_path}': {e}")
        return {"error": str(e)}

@mcp.tool(name="paperless_delete_document")
def delete_document(document_id: int) -> Dict[str, Any]:
    """Permanently delete a document from Paperless-ngx by document ID."""
    try:
        resp = requests.delete(
            f"{PAPERLESS_URL}/api/documents/{document_id}/",
            headers=get_headers(),
            timeout=30,
        )
        resp.raise_for_status()
        logger.info(f"Deleted document {document_id}.")
        return {"deleted": document_id, "status_code": resp.status_code}
    except Exception as e:
        logger.error(f"Failed to delete document {document_id}: {e}")
        return {"error": str(e)}

@mcp.tool(name="paperless_list_tags")
def list_tags() -> List[Dict[str, Any]]:
    """List all tags defined in Paperless-ngx (id, name, document count)."""
    try:
        resp = requests.get(
            f"{PAPERLESS_URL}/api/tags/",
            headers=get_headers(),
            params={"page_size": 100},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"id": t.get("id"), "name": t.get("name"), "document_count": t.get("document_count")}
            for t in data.get("results", [])
        ]
    except Exception as e:
        logger.error(f"Failed to list tags: {e}")
        return [{"error": str(e)}]

@mcp.tool(name="paperless_list_correspondents")
def list_correspondents() -> List[Dict[str, Any]]:
    """List all correspondents defined in Paperless-ngx (id, name, document count)."""
    try:
        resp = requests.get(
            f"{PAPERLESS_URL}/api/correspondents/",
            headers=get_headers(),
            params={"page_size": 100},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {"id": c.get("id"), "name": c.get("name"), "document_count": c.get("document_count")}
            for c in data.get("results", [])
        ]
    except Exception as e:
        logger.error(f"Failed to list correspondents: {e}")
        return [{"error": str(e)}]

if __name__ == "__main__":
    mcp.run()
