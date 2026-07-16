import xmlrpc.client
import os
import sys

TRAC_URL = f"http://will:{os.environ.get('TRAC_PASSWORD', 'YOUR_PASSWORD')}@trac-lxc.home.arpa/login/xmlrpc"

def search_all_tickets(term):
    server = xmlrpc.client.ServerProxy(TRAC_URL)
    # Get all ticket IDs
    query_string = "max=0"
    ticket_ids = server.ticket.query(query_string)
    
    results = []
    for tid in ticket_ids:
        try:
            t = server.ticket.get(tid)
            attributes = t[3]
            desc = attributes.get('description', '')
            summary = attributes.get('summary', '')
            if term in desc or term in summary:
                results.append(f"#{tid}: {summary}")
                continue
                
            # Search comments (changelog)
            changelog = server.ticket.changeLog(tid)
            for change in changelog:
                if change[2] == 'comment':
                    if term in change[4]:
                        results.append(f"#{tid}: {summary}")
                        break
        except Exception as e:
            pass
            
    return results

if __name__ == "__main__":
    term = sys.argv[1]
    print(f"Searching for '{term}'...")
    res = search_all_tickets(term)
    for r in res:
        print(r)
