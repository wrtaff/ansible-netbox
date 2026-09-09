#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/homeassistant/server.py
Version:        1.2
Author:         Antigravity
Last Modified:  2026-09-09
Context:        Home Assistant MCP Stdio Proxy (Trac #4469)
Purpose:        Acts as a stdio-to-HTTP JSON-RPC proxy/bridge for the Home Assistant
                MCP server endpoint to support stdio-only clients like Antigravity.

Revision History:
    v1.0 (2026-06-24): Initial implementation. Simple stdio wrapper that forwards
                       JSON-RPC requests and notifications to Streamable HTTP.
    v1.1 (2026-08-01): Added robust connection/DNS retry logic with exponential
                       backoff to handle transient startup resolution races.
    v1.2 (2026-09-09): Added get_hass_token and get_hass_url fallback loaders
                       (~/.config/mcp-secrets.env, ~/.mcp.json, ~/.bashrc) to
                       ensure token availability in non-interactive subshells and
                       prevent unauthenticated 401s (Trac #4469).

Secrets:
    HASS_TOKEN      (env / ~/.config/mcp-secrets.env) — Home Assistant Long-Lived Access Token for MCP
    HASS_URL        (env / ~/.config/mcp-secrets.env) — Home Assistant MCP endpoint URL

Notes:
    Always bump the version number when modifying this file and annotate
    the changes in the Revision History section.
================================================================================
"""
import sys
import os
import json
import time
import logging
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/homeassistant_mcp_proxy.log',
    filemode='a'
)
logger = logging.getLogger("homeassistant-mcp-proxy")

def get_hass_token():
    """Gets HASS_TOKEN prioritizing environment, ~/.config/mcp-secrets.env, ~/.mcp.json, and ~/.bashrc."""
    token = os.environ.get("HASS_TOKEN")
    if token:
        logger.info("HASS_TOKEN found in environment.")
        return token

    # Try ~/.config/mcp-secrets.env (Ansible-managed environment)
    secrets_file = os.path.expanduser("~/.config/mcp-secrets.env")
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if line.startswith("HASS_TOKEN="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            logger.info("HASS_TOKEN found in ~/.config/mcp-secrets.env.")
                            return val
        except Exception as e:
            logger.error(f"Error reading ~/.config/mcp-secrets.env: {e}")

    # Try ~/.mcp.json
    for config_path in [os.path.expanduser("~/.mcp.json"), "/home/will/pops/.mcp.json"]:
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                    val = config.get("mcpServers", {}).get("homeassistant", {}).get("env", {}).get("HASS_TOKEN")
                    if val and val != "PLACEHOLDER_ROTATE_ME":
                        logger.info(f"HASS_TOKEN found in {config_path}.")
                        return val
            except Exception as e:
                logger.error(f"Error reading {config_path}: {e}")

    # Fallback to ~/.bashrc
    bashrc_path = os.path.expanduser("~/.bashrc")
    if os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "r") as f:
                for line in f:
                    if "export HASS_TOKEN=" in line:
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip('"').strip("'")
                            if val:
                                logger.info("HASS_TOKEN found in ~/.bashrc.")
                                return val
        except Exception as e:
            logger.error(f"Error reading ~/.bashrc: {e}")

    return None

def get_hass_url():
    """Gets HASS_URL prioritizing environment, ~/.config/mcp-secrets.env, and defaults."""
    url = os.environ.get("HASS_URL")
    if url:
        return url

    secrets_file = os.path.expanduser("~/.config/mcp-secrets.env")
    if os.path.exists(secrets_file):
        try:
            with open(secrets_file, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if line.startswith("HASS_URL="):
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
        except Exception:
            pass

    return "http://homeassistant.home.arpa/api/mcp"

def main():
    logger.info("Starting Home Assistant MCP Proxy")
    url = get_hass_url()
    token = get_hass_token()
    
    if not token:
        logger.error("HASS_TOKEN not found in environment, ~/.config/mcp-secrets.env, ~/.mcp.json, or ~/.bashrc")
        sys.stderr.write("Error: HASS_TOKEN environment variable not set and not found in configuration\n")
        sys.exit(1)

        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Read from stdin line-by-line
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
            
        try:
            message = json.loads(line)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON-RPC message: {e}")
            continue
            
        is_notification = "id" not in message
        
        try:
            logger.info(f"Forwarding request to HASS: {message.get('method', 'unknown')} (id: {message.get('id')})")
            
            # Retry loop for transient connection/DNS errors
            max_attempts = 5
            backoff = 1.5
            resp = None
            for attempt in range(1, max_attempts + 1):
                try:
                    resp = requests.post(url, headers=headers, json=message, timeout=30)
                    break
                except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                    if attempt == max_attempts:
                        logger.error(f"Max retries ({max_attempts}) reached for URL {url}: {e}")
                        raise
                    logger.warning(f"Connection attempt {attempt} failed ({e}), retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2.0
            
            if is_notification:
                logger.info(f"Notification sent, response code: {resp.status_code}")
                continue
                
            if resp.status_code == 200:
                response_text = resp.text
                # Ensure the response is on a single line
                response_line = response_text.replace("\n", "").replace("\r", "")
                sys.stdout.write(response_line + "\n")
                sys.stdout.flush()
            else:
                logger.error(f"HTTP error {resp.status_code}: {resp.text}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"HTTP status error: {resp.status_code} - {resp.text}"
                    }
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()
                
        except Exception as e:
            logger.exception("Exception occurred while communicating with HASS MCP API")
            if not is_notification:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Proxy exception: {str(e)}"
                    }
                }
                sys.stdout.write(json.dumps(error_response) + "\n")
                sys.stdout.flush()

if __name__ == "__main__":
    main()
