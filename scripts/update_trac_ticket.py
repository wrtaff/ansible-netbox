#!/usr/bin/env python3
"""
A helper script to update Trac tickets via the XML-RPC API.
"""
import xmlrpc.client
import argparse
import textwrap

# --- Configuration ---
TRAC_URL = "http://will:8675309@trac.home.arpa/login/xmlrpc"
NOTIFY = True

def main():
    """Parses arguments and updates a Trac ticket."""
    parser = argparse.ArgumentParser(
        description="Update an existing Trac ticket.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=textwrap.dedent('''
            Example Usage:
            ./update_trac_ticket.py \
                --ticket-id 2853 \
                --comment "This is my update comment." \
                --action resolve \
                --resolve-as fixed
        ''')
    )

    parser.add_argument("-i", "--ticket-id", required=True, type=int, help="The ID of the ticket to update.")
    parser.add_argument("-c", "--comment", required=True, help="The comment to add to the ticket. Use shell escapes for newlines (e.g., $\'some\\ntext\').")
    parser.add_argument("-d", "--description", help="Update the ticket description. Use shell escapes for newlines (e.g., $\'some\\ntext\').")
    parser.add_argument("-a", "--action", help="The action to perform (e.g., 'resolve', 'reopen').")
    parser.add_argument("-r", "--resolve-as", help="If resolving, the resolution status (e.g., 'fixed', 'wontfix').")
    parser.add_argument("--author", default="gemini", help="The author of the comment.")

    args = parser.parse_args()

    attributes = {}
    if args.description:
        attributes['description'] = args.description
    if args.action:
        attributes['action'] = args.action
    if args.action == 'resolve' and args.resolve_as:
        attributes['action_resolve_resolve_as'] = args.resolve_as

    try:
        print(f"Connecting to Trac server at {TRAC_URL.split('@')[1]}...")
        server = xmlrpc.client.ServerProxy(TRAC_URL)

        # Method signature: ticket.update(id, comment, {attributes}, notify, author)
        server.ticket.update(args.ticket_id, args.comment, attributes, NOTIFY, args.author)

        print(f"\nSuccessfully updated ticket {args.ticket_id}!")
        print(f"  - URL: http://trac.home.arpa/ticket/{args.ticket_id}")

    except xmlrpc.client.Fault as err:
        print(f"\nError: XML-RPC Fault {err.faultCode}")
        print(f"Reason: {err.faultString}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
