import xmlrpc.client
import os
import sys

TRAC_USER = "will"
TRAC_PASSWORD = os.getenv("TRAC_PASSWORD", "8675309")
TRAC_HOST = "trac-lxc.home.arpa"
TRAC_PATH = "/login/xmlrpc"
TRAC_URL = f"http://{TRAC_USER}:{TRAC_PASSWORD}@{TRAC_HOST}{TRAC_PATH}"

def download_attachment(ticket_id, filename):
    server = xmlrpc.client.ServerProxy(TRAC_URL)
    content_rpc = server.ticket.getAttachment(ticket_id, filename)
    with open(filename, "wb") as f:
        f.write(content_rpc.data)
    print(f"Downloaded {filename}")

if __name__ == "__main__":
    download_attachment(int(sys.argv[1]), sys.argv[2])
