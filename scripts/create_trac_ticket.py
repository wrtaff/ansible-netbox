#!/usr/bin/env python3
"""
A helper script to create Trac tickets via the XML-RPC API.
"""
import xmlrpc.client
import argparse
import textwrap

import os

# --- Configuration ---
TRAC_USER = os.getenv("TRAC_USER", "will")
TRAC_PASSWORD = os.getenv("TRAC_PASSWORD")
TRAC_HOST = os.getenv("TRAC_HOST", "trac.home.arpa")
TRAC_PATH = os.getenv("TRAC_PATH", "/login/xmlrpc")

if not TRAC_PASSWORD:
    # Fallback/Safety: Do not run if password is not in env
    print("Error: TRAC_PASSWORD environment variable must be set.")
    exit(1)

TRAC_URL = f"http://{TRAC_USER}:{TRAC_PASSWORD}@{TRAC_HOST}{TRAC_PATH}"
DEFAULT_COMPONENT = "SysAdmin"
DEFAULT_TYPE = "task"
DEFAULT_PRIORITY = "major"
NOTIFY = True

def main():
    """Parses arguments and creates a Trac ticket."""
    parser = argparse.ArgumentParser(
        description="Create a new Trac ticket.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=textwrap.dedent('''
            Example Usage:
            ./create_trac_ticket.py \\
                --summary "Fix the network switch" \\
                --description "First line.\\nSecond line." \\
                --component "Networking" \\
                --keywords "PROV-P3, Maintenance, Hardware" \\
                --milestone "Cycle 3" \\
                --owner "will" \\
                --cc "gemini,anotheruser"
        ''')
    )

    parser.add_argument("-s", "--summary", required=True, help="A brief, descriptive summary of the ticket.")
    parser.add_argument("-d", "--description", required=True, help="The full description of the ticket. Use '\\n' for newlines.")
    parser.add_argument("-c", "--component", default=DEFAULT_COMPONENT, help=f"The component to assign the ticket to. (Default: {DEFAULT_COMPONENT})")
    parser.add_argument("-k", "--keywords", default="", help="Comma-separated keywords for the ticket (e.g., 'PROV-P1, SCM').")
    parser.add_argument("-t", "--type", default=DEFAULT_TYPE, help=f"The type of the ticket. (Default: {DEFAULT_TYPE})")
    parser.add_argument("-p", "--priority", default=DEFAULT_PRIORITY, help=f"The priority of the ticket. (Default: {DEFAULT_PRIORITY})")
    parser.add_argument("-m", "--milestone", default="", help="The milestone to assign the ticket to.")
    parser.add_argument("-o", "--owner", default="", help="The owner to assign the ticket to.")
    parser.add_argument("-a", "--cc", default="", help="A comma-separated list of users to CC on the ticket.")

    args = parser.parse_args()

    # Replace literal '\n' with actual newline characters
    processed_description = args.description.replace('\\n', '\n')

    attributes = {
        'component': args.component,
        'keywords': args.keywords,
        'type': args.type,
        'priority': args.priority,
        'milestone': args.milestone,
        'owner': args.owner,
        'cc': args.cc
    }

    try:
        print(f"Connecting to Trac server at {TRAC_URL.split('@')[1]}...")
        server = xmlrpc.client.ServerProxy(TRAC_URL)

        ticket_id = server.ticket.create(args.summary, processed_description, attributes, NOTIFY)

        print("\nSuccessfully created ticket!")
        print(f"  - ID: {ticket_id}")
        print(f"  - URL: http://trac.home.arpa/ticket/{ticket_id}")

    except xmlrpc.client.Fault as err:
        print(f"\nError: XML-RPC Fault {err.faultCode}")
        print(f"Reason: {err.faultString}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
