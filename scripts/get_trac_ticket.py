#!/usr/bin/env python3
"""
A helper script to retrieve Trac ticket details via the XML-RPC API.
"""
import xmlrpc.client
import argparse
import textwrap

# --- Configuration ---
TRAC_URL = "http://will:8675309@trac.home.arpa/login/xmlrpc"

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
        print(f"Keywords: {attributes.get('keywords', 'N/A')}")
        print("-" * 20)
        print("Description:")
        print(attributes.get('description', ''))

    except xmlrpc.client.Fault as err:
        print(f"\nError: XML-RPC Fault {err.faultCode}")
        print(f"Reason: {err.faultString}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
