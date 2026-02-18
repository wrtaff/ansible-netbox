#!/usr/bin/env python3
"""
A helper script to retrieve the most recent Trac ticket ID.
"""
import xmlrpc.client

import os

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
    """Retrieves the most recent Trac ticket ID."""
    try:
        server = xmlrpc.client.ServerProxy(TRAC_URL)
        ticket_list = server.ticket.query("max=1&order=id&desc=1")
        
        if ticket_list:
            print(ticket_list[0])
        else:
            print("No tickets found.")

    except xmlrpc.client.Fault as err:
        print(f"\nError: XML-RPC Fault {err.faultCode}")
        print(f"Reason: {err.faultString}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()

