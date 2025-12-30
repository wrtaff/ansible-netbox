import os
import requests
import json

NETBOX_URL = "http://netbox1.home.arpa"
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN")

if not NETBOX_TOKEN:
    print("NETBOX_TOKEN environment variable not set.")
    exit(1)

HEADERS = {
    "Authorization": f"Token {NETBOX_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

devices_to_update = [
    {'name': 'hs200-1', 'ip': '192.168.0.120/24'},
    {'name': 'hs200-2', 'ip': '192.168.0.174/24'},
]

def get_device_id_by_name(device_name):
    url = f"{NETBOX_URL}/api/dcim/devices/?name={device_name}"
    response = requests.get(url, headers=HEADERS, verify=False)
    response.raise_for_status()
    devices = response.json().get('results')
    if devices:
        return devices[0]['id']
    return None

def get_ip_address_id(ip_address):
    url = f"{NETBOX_URL}/api/ipam/ip-addresses/?address={ip_address}"
    response = requests.get(url, headers=HEADERS, verify=False)
    response.raise_for_status()
    ips = response.json().get('results')
    if ips:
        return ips[0]['id']
    return None

def set_primary_ip(device_id, ip_address_id):
    device_data = {
        "primary_ip4": ip_address_id
    }
    url = f"{NETBOX_URL}/api/dcim/devices/{device_id}/"
    response = requests.patch(url, headers=HEADERS, json=device_data, verify=False)
    response.raise_for_status()
    return response.json()

def main():
    for device in devices_to_update:
        device_name = device['name']
        ip_address = device['ip']
        
        print(f"Setting primary IP for {device_name}...")
        
        try:
            device_id = get_device_id_by_name(device_name)
            if not device_id:
                print(f"Device {device_name} not found in NetBox. Skipping.")
                continue

            print(f"Found device: {device_name} (ID: {device_id})")

            ip_address_id = get_ip_address_id(ip_address)
            if not ip_address_id:
                print(f"IP address {ip_address} not found in NetBox. Skipping.")
                continue
                
            print(f"Found IP address ID: {ip_address_id}")

            netbox_device = set_primary_ip(device_id, ip_address_id)
            print(f"Successfully set primary IP for {device_name}.")

        except requests.exceptions.RequestException as e:
            print(f"Error setting primary IP for {device_name}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
        print("-" * 30)

if __name__ == "__main__":
    main()
