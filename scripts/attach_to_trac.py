#!/usr/bin/env python3
import xmlrpc.client
import sys
import os
import base64

def attach_to_trac(ticket_id, file_path, description="Uploaded by script"):
    trac_url = "http://will:8675309@trac.home.arpa/login/xmlrpc"
    server = xmlrpc.client.ServerProxy(trac_url)
    
    filename = os.path.basename(file_path)
    with open(file_path, "rb") as f:
        file_data = f.read()
    
    # Binary data must be wrapped in xmlrpc.client.Binary for transfer
    binary_data = xmlrpc.client.Binary(file_data)
    
    try:
        # putAttachment(ticket_id, filename, description, data, replace=True)
        result = server.ticket.putAttachment(ticket_id, filename, description, binary_data, True)
        print(f"Successfully attached {filename} to ticket #{ticket_id}")
        return result
    except Exception as e:
        print(f"Error attaching file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: ./attach_to_trac.py <ticket_id> <file_path> [description]")
        sys.exit(1)
    
    tid = int(sys.argv[1])
    path = sys.argv[2]
    desc = sys.argv[3] if len(sys.argv) > 3 else "Uploaded by script"
    attach_to_trac(tid, path, desc)
