#!/usr/bin/env python3
import os
import sys
import requests
import json

# Configuration
NETBOX_URL = "http://netbox1.home.arpa"
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN")

if not NETBOX_TOKEN:
    print("Error: NETBOX_TOKEN not set.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"Token {NETBOX_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def search_wazuh():
    # Check VMs
    url = f"{NETBOX_URL}/api/virtualization/virtual_machines/?q=wazuh"
    resp = requests.get(url, headers=HEADERS, verify=False)
    if resp.ok:
        print(f"VMs found: {resp.json()['count']}")
        for vm in resp.json()['results']:
            print(f"VM Name: {vm['name']}")
            print(f"Comments: {vm.get('comments', 'No comments')}")
            print("-" * 20)

    # Check Devices
    url = f"{NETBOX_URL}/api/dcim/devices/?q=wazuh"
    resp = requests.get(url, headers=HEADERS, verify=False)
    if resp.ok:
        print(f"Devices found: {resp.json()['count']}")
        for dev in resp.json()['results']:
            print(f"Device Name: {dev['name']}")
            print(f"Comments: {dev.get('comments', 'No comments')}")
            print("-" * 20)

if __name__ == "__main__":
    search_wazuh()