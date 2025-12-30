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
    {'name': 'hs200-1', 'mac': 'ec:75:0c:55:22:3f'},
    {'name': 'hs200-2', 'mac': 'ec:75:0c:55:35:cd'},
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

def update_interface_mac(interface_id, mac_address):
    mac_data = {
        "mac_address": mac_address
    }
    url = f"{NETBOX_URL}/api/dcim/interfaces/{interface_id}/"
    response = requests.patch(url, headers=HEADERS, json=mac_data, verify=False)
    response.raise_for_status()
    return response.json()

def main():
    for device in devices_to_update:
        device_name = device['name']
        mac_address = device['mac']
        
        print(f"Updating MAC address for {device_name}...")
        
        try:
            device_id = get_device_id_by_name(device_name)
            if not device_id:
                print(f"Device {device_name} not found in NetBox. Skipping MAC address update.")
                continue

            print(f"Found device: {device_name} (ID: {device_id})")
            
            interface_id = get_device_interface(device_id)
            if interface_id:
                print(f"Found WiFi interface ID: {interface_id}")
                netbox_interface = update_interface_mac(interface_id, mac_address)
                print(f"Updated MAC address for interface {netbox_interface['name']} to {netbox_interface['mac_address']}.")
            else:
                print(f"Could not find WiFi interface for device {device_name}. Skipping MAC address update.")
                
        except requests.exceptions.RequestException as e:
            print(f"Error updating MAC address for {device_name}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
        print("-" * 30)

if __name__ == "__main__":
    main()
