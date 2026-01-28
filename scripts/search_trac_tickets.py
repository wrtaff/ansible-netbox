import xmlrpc.client
import os

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
    print("Searching for 'audio'...")
    for r in search_tickets("summary~=audio"):
        print(r)
    print("\nSearching for 'transcriber'...")
    for r in search_tickets("summary~=transcriber"):
        print(r)

