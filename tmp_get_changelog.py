import xmlrpc.client
import os

def get_trac_password():
    password = os.getenv("TRAC_PASSWORD")
    if password:
        return password
    return "8675309"

TRAC_USER = "will"
TRAC_PASSWORD = get_trac_password()
TRAC_HOST = "trac-lxc.home.arpa"
TRAC_PATH = "/login/xmlrpc"
TRAC_URL = f"http://{TRAC_USER}:{TRAC_PASSWORD}@{TRAC_HOST}{TRAC_PATH}"

server = xmlrpc.client.ServerProxy(TRAC_URL)
changelog = server.ticket.changeLog(2930)

for i, change in enumerate(changelog):
    print(f"Change {i}: {change}")
