import http.server
import socketserver
import json
import subprocess
import shlex

# --- CONFIGURATION ---
PORT = 9090
VIKUNJA_URL = "https://todo.gafla.us.com"
API_TOKEN = "tk_5c253e3352e8402d8b9c8f7306564a3bec5a329a"
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
                trac_url = shlex.quote(data['tracUrl'])

                # 3. Build the task details
                # Note: shlex.quote adds single quotes, so we build the JSON string carefully.
                task_title = f"#{data['ticketNum']}: {data['summary']}"
                task_desc = f"Trac ticket [#{data['ticketNum']}: {data['summary']}]({data['tracUrl']})"

                json_payload = json.dumps({
                    "title": task_title,
                    "description": task_desc,
                    "is_favorite": True
                })

                # 4. Build the final curl command
                curl_command = [
                    "curl",
                    "-k",  # Bypass self-signed cert
                    "-X", "PUT",
                    f"{VIKUNJA_URL}/api/v1/projects/{project_id}/tasks",
                    "-H", f"Authorization: Bearer {API_TOKEN}",
                    "-H", "Content-Type: application/json",
                    "-d", json_payload
                ]
                
                print("--- Executing Command ---")
                print(" ".join(curl_command))

                # 5. Execute the command
                result = subprocess.run(curl_command, capture_output=True, text=True)

                if result.returncode == 0:
                    print("--- Success ---")
                    print(result.stdout)
                    self.send_response(200)
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(b'{"status": "success"}')
                else:
                    print("--- Error ---")
                    print(result.stderr)
                    self.send_response(500)
                    self._send_cors_headers()
                    self.end_headers()
                    self.wfile.write(b'{"status": "error", "message": "Check server console"}')
            
            except Exception as e:
                print(f"Server Error: {e}")
                self.send_response(500)
                self._send_cors_headers()
                self.end_headers()
                self.wfile.write(b'{"status": "error", "message": "Check server console"}')
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found')

Handler = MyHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://localhost:{PORT}")
    print("Waiting for requests from the Trac bookmarklet...")
    httpd.serve_forever()
