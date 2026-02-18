#!/usr/bin/env python3
"""
A helper script to retrieve Trac ticket attachments via the XML-RPC API.
"""
import xmlrpc.client
import argparse
import os
import base64

# --- Configuration ---
def get_trac_password():
    """Gets the TRAC_PASSWORD, falling back to ~/.bashrc if not set in environment."""
    password = os.getenv("TRAC_PASSWORD")
    if password:
        return password

    bashrc_path = os.path.expanduser("~/.bashrc")
    if os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "r") as f:
                for line in f:
                    if "export TRAC_PASSWORD=" in line:
                        # Extract value: export TRAC_PASSWORD="value" or export TRAC_PASSWORD=value
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip('"').strip("'")
                            return val
        except Exception:
            pass
    return None

TRAC_USER = os.getenv("TRAC_USER", "will")
TRAC_PASSWORD = get_trac_password()
TRAC_HOST = os.getenv("TRAC_HOST", "trac.home.arpa")
TRAC_PATH = os.getenv("TRAC_PATH", "/login/xmlrpc")

if not TRAC_PASSWORD:
    print("Error: TRAC_PASSWORD environment variable must be set (or defined in ~/.bashrc).")
    exit(1)

TRAC_URL = f"http://{TRAC_USER}:{TRAC_PASSWORD}@{TRAC_HOST}{TRAC_PATH}"

def main():
    parser = argparse.ArgumentParser(description="Retrieve attachments for a Trac ticket.")
    parser.add_argument("ticket_id", type=int, help="The ID of the ticket.")
    args = parser.parse_args()

    try:
        server = xmlrpc.client.ServerProxy(TRAC_URL)
        attachments = server.ticket.listAttachments(args.ticket_id)
        
        print(f"Attachments for Ticket #{args.ticket_id}:")
        for attachment in attachments:
            filename = attachment[0]
            print(f"- {filename}")
            # Fetch content for logs
            if "log" in filename:
                content_rpc = server.ticket.getAttachment(args.ticket_id, filename)
                # content_rpc is usually binary data base64 encoded or similar depending on library version
                # In standard xmlrpc.client, Binary objects are returned.
                file_data = content_rpc.data
                print(f"--- Content of {filename} ---")
                try:
                    print(file_data.decode('utf-8'))
                except:
                     print("(Binary content or decode error)")
                print("-----------------------------")

    except xmlrpc.client.Fault as err:
        print(f"Error: {err.faultCode} - {err.faultString}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
