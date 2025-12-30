#!/usr/bin/env python3
"""
Imports NetBox device type definitions from YAML files in the device-types/ directory.
Usage: ./scripts/import_device_types.py
"""
import os
import sys
import yaml
import requests
import glob

# Configuration
NETBOX_URL = "http://netbox1.home.arpa"
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN")
DEVICE_TYPES_DIR = "device-types"

if not NETBOX_TOKEN:
    try:
        with open(os.path.expanduser("~/.bashrc"), "r") as f:
            for line in f:
                if "export NETBOX_TOKEN=" in line:
                    NETBOX_TOKEN = line.split("=")[1].strip().strip('"')
                    break
    except Exception:
        pass

if not NETBOX_TOKEN:
    print("Error: NETBOX_TOKEN not set.", file=sys.stderr)
    sys.exit(1)

HEADERS = {
    "Authorization": f"Token {NETBOX_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def get_manufacturer_id(name):
    url = f"{NETBOX_URL}/api/dcim/manufacturers/?name={name}"
    resp = requests.get(url, headers=HEADERS, verify=False)
    if resp.ok and resp.json()['count'] > 0:
        return resp.json()['results'][0]['id']
    return None

def create_manufacturer(name):
    url = f"{NETBOX_URL}/api/dcim/manufacturers/"
    data = {"name": name, "slug": name.lower().replace(" ", "-")}
    resp = requests.post(url, headers=HEADERS, json=data, verify=False)
    if resp.ok:
        return resp.json()['id']
    return None

def import_device_type(filepath):
    with open(filepath, 'r') as f:
        dt_data = yaml.safe_load(f)

    model = dt_data.get('model')
    slug = dt_data.get('slug')
    manufacturer_name = dt_data.get('manufacturer')

    print(f"Processing {manufacturer_name} {model}...")

    # 1. Handle Manufacturer
    mfr_id = get_manufacturer_id(manufacturer_name)
    if not mfr_id:
        print(f"  Creating manufacturer: {manufacturer_name}")
        mfr_id = create_manufacturer(manufacturer_name)
        if not mfr_id:
            print(f"  Failed to create manufacturer {manufacturer_name}")
            return

    # 2. Check if Device Type exists
    url = f"{NETBOX_URL}/api/dcim/device-types/?slug={slug}"
    resp = requests.get(url, headers=HEADERS, verify=False)
    if resp.ok and resp.json()['count'] > 0:
        print(f"  Device type {model} already exists. Skipping.")
        return
    
    # 3. Create Device Type
    payload = {
        "manufacturer": mfr_id,
        "model": model,
        "slug": slug,
        "part_number": dt_data.get('part_number', ''),
        "u_height": dt_data.get('u_height', 1),
        "is_full_depth": dt_data.get('is_full_depth', True),
        "comments": dt_data.get('comments', '')
    }
    
    create_url = f"{NETBOX_URL}/api/dcim/device-types/"
    resp = requests.post(create_url, headers=HEADERS, json=payload, verify=False)
    
    if resp.status_code == 201:
        new_dt = resp.json()
        print(f"  Successfully created device type: {model}")
        dt_id = new_dt['id']
        
        # 4. Create Components
        # Power Ports
        for pp in dt_data.get('power-ports', []):
            pp_payload = {
                "device_type": dt_id,
                "name": pp['name'],
                "type": pp.get('type', 'iec-60320-c14'),
                "maximum_draw": pp.get('maximum_draw'),
                "allocated_draw": pp.get('allocated_draw')
            }
            requests.post(f"{NETBOX_URL}/api/dcim/power-port-templates/", headers=HEADERS, json=pp_payload, verify=False)
            print(f"    Added Power Port: {pp['name']}")

        # Interfaces
        for iface in dt_data.get('interfaces', []):
            if_payload = {
                "device_type": dt_id,
                "name": iface['name'],
                "type": iface.get('type', '1000base-t'),
                "mgmt_only": iface.get('mgmt_only', False)
            }
            requests.post(f"{NETBOX_URL}/api/dcim/interface-templates/", headers=HEADERS, json=if_payload, verify=False)
            print(f"    Added Interface: {iface['name']}")
            
    else:
        print(f"  Failed to create device type. Error: {resp.text}")

def main():
    if not os.path.isdir(DEVICE_TYPES_DIR):
        print(f"Directory {DEVICE_TYPES_DIR} not found.")
        return

    files = glob.glob(os.path.join(DEVICE_TYPES_DIR, "*.yml"))
    if not files:
        print("No YAML files found in device-types/.")
        return

    for f in files:
        import_device_type(f)

if __name__ == "__main__":
    main()
