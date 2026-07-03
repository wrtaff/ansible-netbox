import xmlrpc.client, os
def get_trac_password():
    with open(os.path.expanduser("~/.bashrc"), "r") as f:
        for line in f:
            if "export TRAC_PASSWORD=" in line:
                return line.split("=", 1)[1].strip().strip('"').strip("'")
TRAC_URL = f"http://will:{get_trac_password()}@trac.home.arpa/login/xmlrpc"
server = xmlrpc.client.ServerProxy(TRAC_URL)
ticket = server.ticket.get(1998)
print("Status:", ticket[3].get('status'))
print("Resolution:", ticket[3].get('resolution'))
