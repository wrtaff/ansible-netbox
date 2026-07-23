#!/usr/bin/env python3
"""
================================================================================
Filename:       local_vikunja_server.py
Version:        1.5
Author:         Will
Last Modified:  2026-07-23
Context:        http://trac.gafla.us.com/ticket/2790, http://trac.gafla.us.com/ticket/3999

Purpose:
    Lightweight HTTP bridge between the Trac bookmarklet (trac2vik.js) and the
    Vikunja API. Receives POST requests containing Trac ticket details and
    creates corresponding tasks in Vikunja using a secure API token supplied
    via environment variable.

Usage:
    Managed as a systemd service (vikunja-helper) on gmailctl-ansible.
    VIKUNJA_API_TOKEN environment variable must be set in the service unit.
    Deploy path: /opt/vikunja-helper/local_vikunja_server.py
    Ansible playbook: playbooks/deploy_trac_vik_servlet_helper.yml

Notes:
    Always bump version and annotate changes in this header when modifying.
    Related ticket: http://trac.gafla.us.com/ticket/2963 (urllib refactor)
================================================================================
"""
import http.server
import socketserver
import json
import subprocess
import shlex
import urllib.request
import urllib.error
import ssl
import os

# --- CONFIGURATION ---
PORT = 9090
VIKUNJA_URL = "http://todo.home.arpa"
API_TOKEN = os.getenv("VIKUNJA_API_TOKEN")

if not API_TOKEN:
    print("Error: VIKUNJA_API_TOKEN environment variable is not set.")
# ---------------------

class MyHandler(http.server.SimpleHTTPRequestHandler):
    
    def _send_cors_headers(self):
        """Send headers to allow Cross-Origin Resource Sharing (CORS)"""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        """Respond to a CORS preflight request."""
        self.send_response(204) # No Content
        self._send_cors_headers()
        self.end_headers()

    def do_POST(self):
        """Handle the incoming POST request from the bookmarklet."""
        if self.path == "/create-task":
            try:
                # 1. Read the incoming JSON data
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)

                # 2. Extract data
                # We do not use shlex.quote because we are passing arguments as a list to subprocess.run,
                # which avoids shell injection. Quoting here would corrupt the JSON data and URL.
                project_id = str(data['projectId'])
                ticket_num = str(data['ticketNum'])
                # Sanitize summary to remove newlines, which break Markdown links
                summary = str(data['summary']).replace('\n', ' ').replace('\r', ' ').strip()
                trac_url_raw = data['tracUrl'].strip()
                
                # Remove anchor from URL (e.g. #comment:1) and fix domain
                trac_url_clean = trac_url_raw.split('#')[0]
                trac_url_final = trac_url_clean.replace('trac.home.arpa', 'trac.gafla.us.com')

                # 3. Build the task details (HTML format is parsed by Vikunja/Tiptap natively)
                task_title = f"#{ticket_num}: {summary}"
                task_desc = f'<p><a href="{trac_url_final}">Trac #{ticket_num}: {summary}</a></p>'

                json_payload = json.dumps({
                    "title": task_title,
                    "description": task_desc,
                    "is_favorite": True
                })

                # 4. Prepare Request (Python native, no curl)
                url = f"{VIKUNJA_URL}/api/v1/projects/{project_id}/tasks"
                headers = {
                    "Authorization": f"Bearer {API_TOKEN}",
                    "Content-Type": "application/json"
                }
                
                # Create SSL context (unverified, same as curl -k)
                ctx = ssl.create_default_context()
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE

                req = urllib.request.Request(url, data=json_payload.encode('utf-8'), headers=headers, method="PUT")

                # Generate a curl command string for display/logging only
                curl_command_str = f"curl -k -X PUT {url} -H 'Authorization: Bearer ***' -H 'Content-Type: application/json' -d '{json_payload}'"
                print("--- Executing Request (via Python urllib) ---", flush=True)
                print(f"URL: {url}", flush=True)

                # 5. Execute
                try:
                    with urllib.request.urlopen(req, context=ctx) as response:
                        response_body = response.read().decode('utf-8')
                        print("--- Success ---", flush=True)
                        print(response_body, flush=True)
                        
                        self.send_response(200)
                        self._send_cors_headers()
                        self.end_headers()
                        
                        self.wfile.write(json.dumps({
                            "status": "success",
                            "curl_command": curl_command_str,
                            "stdout": response_body,
                            "stderr": ""
                        }).encode('utf-8'))

                except urllib.error.HTTPError as e:
                    error_body = e.read().decode('utf-8')
                    print(f"--- HTTP Error {e.code} ---", flush=True)
                    print(error_body, flush=True)
                    
                    self.send_response(500)
                    self._send_cors_headers()
                    self.end_headers()
                    
                    self.wfile.write(json.dumps({
                        "status": "error",
                        "message": f"HTTP {e.code}: {e.reason}",
                        "curl_command": curl_command_str,
                        "stderr": error_body
                    }).encode('utf-8'))

                except Exception as e:
                    raise e # Re-raise to be caught by outer try/except

            except Exception as e:
                print(f"Server Error: {e}", flush=True)
                self.send_response(500)
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "error", 
                    "message": str(e)
                }).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

Handler = MyHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://localhost:{PORT}")
    print("Waiting for requests from the Trac bookmarklet...")
    httpd.serve_forever()
