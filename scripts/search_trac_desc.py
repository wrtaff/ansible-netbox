import xmlrpc.client
import os
import sys

TRAC_URL = f"http://will:{os.environ.get('TRAC_PASSWORD', 'YOUR_PASSWORD')}@trac-lxc.home.arpa/login/xmlrpc"

def search_desc(term):
    server = xmlrpc.client.ServerProxy(TRAC_URL)
    # Get ticket IDs where description contains the term
    query_string = f"description~={term}"
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
    term = sys.argv[1]
    print(f"Searching for '{term}'...")
    res = search_desc(term)
    for r in res:
        print(r)
