#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/homeassistant/server.py
Version:        1.0
Author:         Antigravity
Last Modified:  2026-06-24
Context:        Home Assistant MCP Stdio Proxy
Purpose:        Acts as a stdio-to-HTTP JSON-RPC proxy/bridge for the Home Assistant
                MCP server endpoint to support stdio-only clients like Antigravity.

Revision History:
    v1.0 (2026-06-24): Initial implementation. Simple stdio wrapper that forwards
                       JSON-RPC requests and notifications to Streamable HTTP.

Secrets:
    HASS_TOKEN      (env) — Home Assistant Long-Lived Access Token for MCP
    HASS_URL        (env) — Home Assistant MCP endpoint URL

Notes:
    Always bump the version number when modifying this file and annotate
    the changes in the Revision History section.
================================================================================
"""
import sys
import os
import json
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

def main():
    logger.info("Starting Home Assistant MCP Proxy")
    url = os.environ.get("HASS_URL", "http://hass.home.arpa/api/mcp")
    token = os.environ.get("HASS_TOKEN")
    
    if not token:
        logger.error("HASS_TOKEN environment variable not set")
        sys.stderr.write("Error: HASS_TOKEN environment variable not set\n")
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
            resp = requests.post(url, headers=headers, json=message, timeout=30)
            
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
