#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/porkbun_manager.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-03-11
Context:        http://trac.gafla.us.com/ticket/3169

Purpose:
    Manager for Porkbun DNS records via API.
    Provides functionality to list, create, and delete DNS records.

Usage:
    python3 porkbun_manager.py list <domain>
    python3 porkbun_manager.py create <domain> <type> <name> <content> [ttl] [prio]
    python3 porkbun_manager.py delete <domain> <id>

Revision History:
    v1.0 (2026-03-11): Initial version with list, create, and delete support.

Notes:
    Requires PORKBUN_API_KEY and PORKBUN_SECRET_KEY environment variables.
================================================================================
"""

import os
import sys
import json
import requests
import argparse

API_BASE = "https://api.porkbun.com/api/json/v3"

def get_credentials():
    api_key = os.environ.get("PORKBUN_API_KEY")
    secret_key = os.environ.get("PORKBUN_SECRET_KEY")
    if not api_key or not secret_key:
        print("Error: PORKBUN_API_KEY and PORKBUN_SECRET_KEY must be set.")
        sys.exit(1)
    return api_key, secret_key

def porkbun_post(endpoint, data=None):
    api_key, secret_key = get_credentials()
    url = f"{API_BASE}/{endpoint}"
    payload = {
        "apikey": api_key,
        "secretapikey": secret_key
    }
    if data:
        payload.update(data)
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"API Request Failed: {e}")
        if hasattr(e.response, 'text'):
            print(f"Response: {e.response.text}")
        sys.exit(1)

def list_records(domain, output_format='text'):
    result = porkbun_post(f"dns/retrieve/{domain}")
    if result.get("status") == "SUCCESS":
        records = result.get("records", [])
        if output_format == 'json':
            print(json.dumps(records, indent=2))
        else:
            print(f"{'ID':<12} {'Type':<6} {'Name':<30} {'Content':<40} {'TTL':<6}")
            print("-" * 100)
            for r in records:
                print(f"{r['id']:<12} {r['type']:<6} {r['name']:<30} {r['content']:<40} {r['ttl']:<6}")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")

def create_record(domain, dtype, name, content, ttl=600, prio=None):
    data = {
        "name": name,
        "type": dtype,
        "content": content,
        "ttl": str(ttl)
    }
    if prio:
        data["prio"] = str(prio)
    
    result = porkbun_post(f"dns/create/{domain}", data)
    if result.get("status") == "SUCCESS":
        print(f"Successfully created record. ID: {result.get('id')}")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")

def delete_record(domain, record_id):
    result = porkbun_post(f"dns/delete/{domain}/{record_id}")
    if result.get("status") == "SUCCESS":
        print(f"Successfully deleted record {record_id}")
    else:
        print(f"Error: {result.get('message', 'Unknown error')}")

def main():
    parser = argparse.ArgumentParser(description="Porkbun DNS Manager")
    subparsers = parser.add_subparsers(dest="command")

    # List command
    list_parser = subparsers.add_parser("list", help="List DNS records for a domain")
    list_parser.add_argument("domain", help="The domain name (e.g., gafla.us.com)")
    list_parser.add_argument("--json", action="store_true", help="Output in JSON format")

    # Create command
    create_parser = subparsers.add_parser("create", help="Create a DNS record")
    create_parser.add_argument("domain", help="The domain name")
    create_parser.add_argument("type", help="Record type (A, CNAME, MX, etc.)")
    create_parser.add_argument("name", help="Subdomain or record name")
    create_parser.add_argument("content", help="Record content/value")
    create_parser.add_argument("--ttl", type=int, default=600, help="TTL (default 600)")
    create_parser.add_argument("--prio", help="Priority (for MX/SRV)")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a DNS record")
    delete_parser.add_argument("domain", help="The domain name")
    delete_parser.add_argument("id", help="The record ID")

    args = parser.parse_args()

    if args.command == "list":
        list_records(args.domain, 'json' if args.json else 'text')
    elif args.command == "create":
        create_record(args.domain, args.type.upper(), args.name, args.content, args.ttl, args.prio)
    elif args.command == "delete":
        delete_record(args.domain, args.id)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
