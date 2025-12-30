#!/usr/bin/env python3
"""
A helper script to retrieve the most recent Trac ticket ID.
"""
import xmlrpc.client

import os

# --- Configuration ---
TRAC_USER = os.getenv("TRAC_USER", "will")
TRAC_PASSWORD = os.getenv("TRAC_PASSWORD")
TRAC_HOST = os.getenv("TRAC_HOST", "trac.home.arpa")
TRAC_PATH = os.getenv("TRAC_PATH", "/login/xmlrpc")

if not TRAC_PASSWORD:
    print("Error: TRAC_PASSWORD environment variable must be set.")
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

