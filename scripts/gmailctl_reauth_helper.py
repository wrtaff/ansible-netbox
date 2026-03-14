#!/usr/bin/env python3
import subprocess
import re
import sys
import time

def get_gmailctl_init_info(host_ip="192.168.0.25"):
    """
    Starts 'gmailctl init' on the remote host inside a tmux session, 
    captures the authorization URL and dynamic port, and keeps it running.
    """
    print(f"[*] Stopping any existing gmailctl processes and tmux sessions on {host_ip}...")
    subprocess.run(["ssh", f"root@{host_ip}", "pkill -f gmailctl || true"], capture_output=True)
    subprocess.run(["ssh", f"root@{host_ip}", "tmux kill-session -t gmailctl_auth || true"], capture_output=True)

    print(f"[*] Starting 'gmailctl init' on {host_ip} inside tmux...")
    # Start tmux and gmailctl
    subprocess.run([
        "ssh", f"root@{host_ip}", 
        "tmux new-session -d -s gmailctl_auth '/root/go/bin/gmailctl init'"
    ])

    url = None
    port = None
    timeout = 15
    start_time = time.time()
    
    print("[*] Waiting for authorization URL...")
    while time.time() - start_time < timeout:
        # Capture the tmux buffer
        res = subprocess.run([
            "ssh", f"root@{host_ip}", 
            "tmux capture-pane -t gmailctl_auth -p"
        ], capture_output=True, text=True)
        
        output = res.stdout
        # Look for the URL
        match = re.search(r"(https://accounts\.google\.com/[^\s]+)", output)
        if match:
            url = match.group(1)
            # Extract port
            port_match = re.search(r"localhost%3A(\d+)", url)
            if port_match:
                port = port_match.group(1)
            break
        time.sleep(1)

    if not url or not port:
        print("[!] Failed to capture URL or Port from tmux buffer.")
        sys.exit(1)

    print(f"[+] Captured Port: {port}")
    print(f"[+] Captured URL: {url}")
    
    return url, port

def generate_trac_comment(ticket_id, url, port, host_ip="192.168.0.25"):
    comment = f"""=== Gmailctl Re-authentication (via Tmux) ===

The Gmailctl token has expired. Please follow these steps:

**1. Authorization Link:**
[{url} Click here to authorize]

**2. SSH Tunnel Command (Run this on limbo-bd):**
{{{{{{
ssh -L {port}:localhost:{port} will@{host_ip}
}}}}}}

**3. Refresh the Browser:**
After starting the tunnel, click the link above or refresh the page.

*Note: The authorization server is running inside a tmux session on {host_ip} and will persist until the token is saved.*"""
    return comment

if __name__ == "__main__":
    TICKET_ID = 2639
    url, port = get_gmailctl_init_info()
    comment = generate_trac_comment(TICKET_ID, url, port)
    
    print("--- TRAC COMMENT START ---")
    print(comment)
    print("--- TRAC COMMENT END ---")
    print("[*] Tmux session 'gmailctl_auth' is active on 192.168.0.25.")
