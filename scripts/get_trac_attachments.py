#!/usr/bin/env python3
"""
A helper script to retrieve Trac ticket attachments via the XML-RPC API.
"""
import xmlrpc.client
import argparse
import os
import base64

# --- Configuration ---
TRAC_USER = os.getenv("TRAC_USER", "will")
TRAC_PASSWORD = os.getenv("TRAC_PASSWORD")
TRAC_HOST = os.getenv("TRAC_HOST", "trac.home.arpa")
TRAC_PATH = os.getenv("TRAC_PATH", "/login/xmlrpc")

if not TRAC_PASSWORD:
    print("Error: TRAC_PASSWORD environment variable must be set.")
    exit(1)

TRAC_URL = f"http://{TRAC_USER}:{TRAC_PASSWORD}@{TRAC_HOST}{TRAC_PATH}"

def main():
    parser = argparse.ArgumentParser(description="Retrieve attachments for a Trac ticket.")
    parser.add_argument("ticket_id", type=int, help="The ID of the ticket.")
    args = parser.parse_args()

    try:
        server = xmlrpc.client.ServerProxy(TRAC_URL)
        attachments = server.ticket.listAttachments(args.ticket_id)
        
        print(f"Attachments for Ticket #{args.ticket_id}:")
        for attachment in attachments:
            filename = attachment[0]
            print(f"- {filename}")
            # Fetch content for logs
            if "log" in filename:
                content_rpc = server.ticket.getAttachment(args.ticket_id, filename)
                # content_rpc is usually binary data base64 encoded or similar depending on library version
                # In standard xmlrpc.client, Binary objects are returned.
                file_data = content_rpc.data
                print(f"--- Content of {filename} ---")
                try:
                    print(file_data.decode('utf-8'))
                except:
                     print("(Binary content or decode error)")
                print("-----------------------------")

    except xmlrpc.client.Fault as err:
        print(f"Error: {err.faultCode} - {err.faultString}")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()
