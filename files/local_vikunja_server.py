import http.server
import socketserver
import json
import subprocess
import shlex

# --- CONFIGURATION ---
PORT = 9090
VIKUNJA_URL = "http://todo.home.arpa"
API_TOKEN = "tk_19174c6c76e7f5a809c952d410d3fba1db3c03d6"
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

                # 2. Extract data (and sanitize it for shell safety)
                project_id = shlex.quote(data['projectId'])
                ticket_num = shlex.quote(data['ticketNum'])
                summary = shlex.quote(data['summary'])
                trac_url_raw = data['tracUrl']
                
                # Remove anchor from URL (e.g. #comment:1)
                trac_url_clean = trac_url_raw.split('#')[0]
                trac_url = shlex.quote(trac_url_clean)

                # 3. Build the task details
                # Note: shlex.quote adds single quotes, so we build the JSON string carefully.
                task_title = f"#{data['ticketNum']}: {data['summary']}"
                task_desc = f"Trac ticket [#{data['ticketNum']}: {data['summary']}]({trac_url_clean})"

                json_payload = json.dumps({
                    "title": task_title,
                    "description": task_desc,
                    "is_favorite": True
                })

                # 4. Build the final curl command
                curl_command_list = [
                    "/usr/bin/curl",
                    "-k",  # Bypass self-signed cert
                    "-X", "PUT",
                    f"{VIKUNJA_URL}/api/v1/projects/{project_id}/tasks",
                    "-H", f"Authorization: Bearer {API_TOKEN}",
                    "-H", "Content-Type: application/json",
                    "-d", json_payload
                ]
                
                # Create a safe string representation for display/logging (redacting token if desired, but user asked for it)
                # We will keep the token visible as requested for troubleshooting.
                curl_command_str = " ".join(curl_command_list)

                print("--- Executing Command ---", flush=True)
                print(curl_command_str, flush=True)

                # 5. Execute the command
                result = subprocess.run(curl_command_list, capture_output=True, text=True)

                response_data = {
                    "curl_command": curl_command_str,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }

                if result.returncode == 0:
                    print("--- Success ---", flush=True)
                    print(result.stdout, flush=True)
                    self.send_response(200)
                    self._send_cors_headers()
                    self.end_headers()
                    response_data["status"] = "success"
                    self.wfile.write(json.dumps(response_data).encode('utf-8'))
                else:
                    print("--- Error ---", flush=True)
                    print(result.stderr, flush=True)
                    self.send_response(500)
                    self._send_cors_headers()
                    self.end_headers()
                    response_data["status"] = "error"
                    response_data["message"] = "Command failed"
                    self.wfile.write(json.dumps(response_data).encode('utf-8'))
            
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
