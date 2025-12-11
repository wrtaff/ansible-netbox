#!/usr/bin/env python3
"""
A helper script to retrieve the most recent Trac ticket ID.
"""
import xmlrpc.client

# --- Configuration ---
TRAC_URL = "http://will:8675309@trac.home.arpa/login/xmlrpc"

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

