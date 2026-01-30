import xmlrpc.client
import os
import sys

TRAC_URL = "http://will:8675309@trac-lxc.home.arpa/login/xmlrpc"

def search_tickets(query_string):
    try:
        server = xmlrpc.client.ServerProxy(TRAC_URL)
        # ticket.query returns a list of ticket IDs
        ticket_ids = server.ticket.query(query_string)
        
        results = []
        for tid in ticket_ids:
            # ticket.get returns [id, time_created, time_changed, attributes]
            t = server.ticket.get(tid)
            attributes = t[3]
            results.append(f"#{tid}: {attributes.get('summary')} (Status: {attributes.get('status')})")
            
        return results
    except Exception as e:
        return [f"Error: {e}"]

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 search_trac_tickets.py <search_term>")
        sys.exit(1)

    search_term = sys.argv[1]
    query = f"summary~={search_term}"
    print(f"Searching for '{search_term}'...")
    for r in search_tickets(query):
        print(r)