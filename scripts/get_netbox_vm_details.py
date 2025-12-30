#!/usr/bin/env python3
"""
Retrieves details for a specific Virtual Machine from NetBox.
Usage: ./get_netbox_vm_details.py <vm_name>
"""
import os
import sys
import requests
import json
import argparse

# Configuration
NETBOX_URL = "http://netbox1.home.arpa"
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN")

if not NETBOX_TOKEN:
    # Try reading from ~/.bashrc if environment variable is not set
    try:
        with open(os.path.expanduser("~/.bashrc"), "r") as f:
            for line in f:
                if "export NETBOX_TOKEN=" in line:
                    NETBOX_TOKEN = line.split("=")[1].strip().strip('"')
                    break
    except Exception:
        pass

if not NETBOX_TOKEN:
    print("Error: NETBOX_TOKEN environment variable not set.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"Token {NETBOX_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def get_vm_details(vm_name):
    """Fetches full details for a VM by name."""
    url = f"{NETBOX_URL}/api/virtualization/virtual-machines/"
    params = {"name": vm_name}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, verify=False)
        response.raise_for_status()
        data = response.json()
        
        if data["count"] == 0:
            print(f"Error: No VM found with name '{vm_name}'", file=sys.stderr)
            return None
        
        return data["results"][0]
        
    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}", file=sys.stderr)
        if hasattr(e, 'response') and e.response is not None:
             print(f"Response: {e.response.text}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Get NetBox VM details.")
    parser.add_argument("vm_name", help="Name of the Virtual Machine")
    args = parser.parse_args()

    vm = get_vm_details(args.vm_name)
    
    if vm:
        print("-" * 40)
        print(f"VM: {vm.get('name')} (ID: {vm.get('id')})")
        print("-" * 40)
        print(f"Status: {vm.get('status', {}).get('value')}")
        print(f"vCPUs: {vm.get('vcpus')}")
        print(f"Memory: {vm.get('memory')} MB")
        print(f"Disk: {vm.get('disk')} GB")
        
        comments = vm.get('comments')
        print("-" * 40)
        print("Comments:")
        if comments:
            print(comments)
        else:
            print("(None)")
            
        custom_fields = vm.get('custom_fields')
        if custom_fields:
            print("-" * 40)
            print("Custom Fields:")
            print(json.dumps(custom_fields, indent=2))

if __name__ == "__main__":
    main()
