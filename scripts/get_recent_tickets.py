import xmlrpc.client
import os
import sys

TRAC_URL = f"http://will:{os.environ.get('TRAC_PASSWORD', 'YOUR_PASSWORD')}@trac-lxc.home.arpa/login/xmlrpc"

def get_recent():
    server = xmlrpc.client.ServerProxy(TRAC_URL)
    # Get recent tickets sorted by created or modified
    query_string = "status!=closed&order=changetime&desc=1&max=20"
    ticket_ids = server.ticket.query(query_string)
    
    results = []
    for tid in ticket_ids:
        try:
            t = server.ticket.get(tid)
            attributes = t[3]
            summary = attributes.get('summary', '')
            results.append(f"#{tid}: {summary}")
        except Exception as e:
            pass
            
    return results

if __name__ == "__main__":
    res = get_recent()
    for r in res:
        print(r)
