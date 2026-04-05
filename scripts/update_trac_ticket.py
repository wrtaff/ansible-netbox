#!/usr/bin/env python3
"""
================================================================================
Filename:       update_trac_ticket.py
Version:        1.6
Author:         Gemini CLI
Last Modified:  2026-04-02
Context:        http://trac.home.arpa/ticket/3265
WWOS:           http://192.168.0.99/mediawiki/index.php/Trac_Wiki_Formatter

Purpose:
    A helper script to update Trac tickets via the XML-RPC API.

    Update 1.6:
    - Finalized integration with scripts.lib.trac_formatter.
    Update 1.5:
    - Integrated scripts.lib.trac_formatter for MoinMoin formatting.
    - Added --markdown (-m) flag for automated Markdown-to-MoinMoin conversion.
    - Added automated secret sanitization for all comments and descriptions.
    - Updated header to WWOS standard with Context and WWOS links.
================================================================================
"""
import xmlrpc.client
import argparse
import textwrap
import os
import sys

# Ensure scripts/lib is in path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from lib.trac_formatter import markdown_to_moinmoin, sanitize_content

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
NOTIFY = True

def main():
    """Parses arguments and updates a Trac ticket."""
    parser = argparse.ArgumentParser(
        description="Update an existing Trac ticket.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=textwrap.dedent('''
            Example Usage:
            ./update_trac_ticket.py \\
                --ticket-id 2853 \\
                --comment "This is my update comment.\\nThis is a new line." \\
                --action resolve \\
                --resolve-as fixed
        ''')
    )

    parser.add_argument("-i", "--ticket-id", required=True, type=int, help="The ID of the ticket to update.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--comment", help="The comment to add to the ticket. Use '\\n' for newlines.")
    group.add_argument("-f", "--comment-file", help="Path to a file containing the comment text.")
    
    parser.add_argument("-s", "--summary", help="Update the ticket summary.")
    parser.add_argument("-d", "--description", help="Update the ticket description. Use '\\n' for newlines.")
    parser.add_argument("-a", "--action", help="The action to perform (e.g., 'resolve', 'reopen').")
    parser.add_argument("-r", "--resolve-as", help="If resolving, the resolution status (e.g., 'fixed', 'wontfix').")
    parser.add_argument("-p", "--priority", help="Update the ticket priority (e.g., 'major', 'minor').")
    parser.add_argument("-k", "--keywords", help="Update the ticket keywords (e.g., 'networking dns'). Commas will be automatically replaced with spaces.")
    parser.add_argument("-m", "--markdown", action="store_true", help="Convert comment and description from Markdown to MoinMoin syntax.")
    parser.add_argument("--author", default="gemini", help="The author of the comment.")

    args = parser.parse_args()

    # Enforce correct line break encoding for comments
    if args.comment and '&#10;' in args.comment:
        print("Error: Incorrect line break encoding detected in comment. Do not use XML entities like '&#10;'. Use '\\n' for newlines.")
        exit(1)

    if args.description and '&#10;' in args.description:
        print("Error: Incorrect line break encoding detected in description. Do not use XML entities like '&#10;'. Use '\\n' for newlines.")
        exit(1)

    comment_text = ""
    if args.comment_file:
        try:
            with open(args.comment_file, "r") as f:
                comment_text = f.read()
        except Exception as e:
            print(f"Error reading comment file: {e}")
            exit(1)
    elif args.comment:
        # Replace literal '\n' with actual newline characters
        comment_text = args.comment.replace("\\n", "\n")

    # Apply formatting and sanitization to comment
    if args.markdown:
        comment_text = markdown_to_moinmoin(comment_text)
    comment_text = sanitize_content(comment_text)

    attributes = {}
    if args.summary:
        attributes['summary'] = args.summary
    if args.description:
        # Replace literal '\n' with actual newline characters
        desc = args.description.replace("\\n", "\n")
        if args.markdown:
            desc = markdown_to_moinmoin(desc)
        attributes['description'] = sanitize_content(desc)

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