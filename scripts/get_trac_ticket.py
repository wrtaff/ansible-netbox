#!/usr/bin/env python3
"""
A helper script to retrieve Trac ticket details via the XML-RPC API.
"""
import xmlrpc.client
import argparse
import textwrap

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
    """Parses arguments and retrieves a Trac ticket."""
    parser = argparse.ArgumentParser(
        description="Retrieve details for a Trac ticket.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("ticket_id", type=int, help="The ID of the ticket to retrieve.")
    args = parser.parse_args()

    try:
        server = xmlrpc.client.ServerProxy(TRAC_URL)
        ticket = server.ticket.get(args.ticket_id)
        
        # The result is a list: [id, time_created, time_changed, attributes]
        attributes = ticket[3]
        
        print(f"Ticket: #{ticket[0]}")
        print(f"Summary: {attributes.get('summary', 'N/A')}")
        print(f"Status: {attributes.get('status', 'N/A')}")
        print(f"Priority: {attributes.get('priority', 'N/A')}")
        print(f"Keywords: {attributes.get('keywords', 'N/A')}")
        print("-" * 20)
        print("Description:")
        print(attributes.get('description', ''))

        print("\n" + "-" * 20)
        print("Comments:")
        changelog = server.ticket.changeLog(args.ticket_id)
        for change in changelog:
            # Change structure: [time, author, field, oldvalue, newvalue, permanent]
            field = change[2]
            if field == 'comment':
                author = change[1]
                timestamp = change[0]
                comment_text = change[4]
                if comment_text:
                    print(f"\n--- {author} at {timestamp} ---")
                    print(comment_text)

    except xmlrpc.client.Fault as err:
        print(f"\nError: XML-RPC Fault {err.faultCode}")
        print(f"Reason: {err.faultString}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
