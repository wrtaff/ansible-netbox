#!/usr/bin/env python3
"""
================================================================================
Filename:       update_trac_ticket.py
Version:        1.1
Author:         Gemini CLI
Last Modified:  2026-01-26
Context:        http://trac.home.arpa/ticket/2965

Purpose:
    A helper script to update Trac tickets via the XML-RPC API.

    Update 1.1:
    - Enforced space-separated keywords by automatically replacing commas.

Usage:
    ./update_trac_ticket.py --help
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
    print("Error: TRAC_PASSWORD environment variable must be set.")
    exit(1)

TRAC_URL = f"http://{TRAC_USER}:{TRAC_PASSWORD}@{TRAC_HOST}{TRAC_PATH}"
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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--comment", help="The comment to add to the ticket. Use shell escapes for newlines (e.g., $\'some\\ntext\').")
    group.add_argument("-f", "--comment-file", help="Path to a file containing the comment text.")
    
    parser.add_argument("-s", "--summary", help="Update the ticket summary.")
    parser.add_argument("-d", "--description", help="Update the ticket description. Use shell escapes for newlines (e.g., $\'some\\ntext\').")
    parser.add_argument("-a", "--action", help="The action to perform (e.g., 'resolve', 'reopen').")
    parser.add_argument("-r", "--resolve-as", help="If resolving, the resolution status (e.g., 'fixed', 'wontfix').")
    parser.add_argument("-p", "--priority", help="Update the ticket priority (e.g., 'major', 'minor').")
    parser.add_argument("-k", "--keywords", help="Update the ticket keywords (e.g., 'networking dns'). Commas will be automatically replaced with spaces.")
    parser.add_argument("--author", default="gemini", help="The author of the comment.")

    args = parser.parse_args()

    comment_text = ""
    if args.comment_file:
        try:
            with open(args.comment_file, "r") as f:
                comment_text = f.read()
        except Exception as e:
            print(f"Error reading comment file: {e}")
            exit(1)
    elif args.comment:
        comment_text = args.comment.replace("\\n", "\n")

    attributes = {}
    if args.summary:
        attributes['summary'] = args.summary
    if args.description:
        attributes['description'] = args.description.replace("\\n", "\n")
    if args.action:
        attributes['action'] = args.action
    if args.action == 'resolve' and args.resolve_as:
        attributes['action_resolve_resolve_as'] = args.resolve_as
    if args.priority:
        attributes['priority'] = args.priority
    if args.keywords:
        attributes['keywords'] = args.keywords.replace(',', ' ')

    try:
        print(f"Connecting to Trac server at {TRAC_URL.split('@')[1]}...")
        server = xmlrpc.client.ServerProxy(TRAC_URL)

        # Method signature: ticket.update(id, comment, {attributes}, notify, author)
        server.ticket.update(args.ticket_id, comment_text, attributes, NOTIFY, args.author)

        print(f"\nSuccessfully updated ticket {args.ticket_id}!")
        print(f"  - URL: http://trac.home.arpa/ticket/{args.ticket_id}")

    except xmlrpc.client.Fault as err:
        print(f"\nError: XML-RPC Fault {err.faultCode}")
        print(f"Reason: {err.faultString}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
