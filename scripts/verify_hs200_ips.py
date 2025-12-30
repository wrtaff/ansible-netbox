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

devices_to_verify = [
    {'name': 'hs200-1'},
    {'name': 'hs200-2'},
]

def get_device_id_by_name(device_name):
    url = f"{NETBOX_URL}/api/dcim/devices/?name={device_name}"
    response = requests.get(url, headers=HEADERS, verify=False)
    response.raise_for_status()
    devices = response.json().get('results')
    if devices:
        return devices[0]['id']
    return None

def get_device_interface(device_id):
    url = f"{NETBOX_URL}/api/dcim/interfaces/?device_id={device_id}&name=WiFi"
    response = requests.get(url, headers=HEADERS, verify=False)
    response.raise_for_status()
    interfaces = response.json().get('results')
    if interfaces:
        return interfaces[0]['id']
    return None

def get_interface_ip(interface_id):
    url = f"{NETBOX_URL}/api/ipam/ip-addresses/?interface_id={interface_id}"
    response = requests.get(url, headers=HEADERS, verify=False)
    response.raise_for_status()
    ips = response.json().get('results')
    if ips:
        return ips[0]['address']
    return None

def main():
    for device in devices_to_verify:
        device_name = device['name']
        
        print(f"Verifying IP for {device_name}...")
        
        try:
            device_id = get_device_id_by_name(device_name)
            if not device_id:
                print(f"Device {device_name} not found in NetBox.")
                continue

            print(f"Found device: {device_name} (ID: {device_id})")
            
            interface_id = get_device_interface(device_id)
            if interface_id:
                print(f"Found WiFi interface ID: {interface_id}")
                
                assigned_ip = get_interface_ip(interface_id)
                if assigned_ip:
                    print(f"Verification successful: Found IP {assigned_ip} for interface {interface_id}")
                else:
                    print(f"Verification failed: Could not find IP for interface {interface_id}")
            else:
                print(f"Could not find WiFi interface for device {device_name}.")
                
        except requests.exceptions.RequestException as e:
            print(f"Error verifying IP for {device_name}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
        print("-" * 30)

if __name__ == "__main__":
    main()
