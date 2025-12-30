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
    {'name': 'hs103-a3', 'mac': 'd8:07:b6:aa:0d:a3'},
    {'name': 'hs103-a929', 'mac': '3c:52:a1:21:a9:29'},
    {'name': 'HS103', 'mac': '3c:52:a1:21:c7:c9'},
    {'name': 'hs103-29', 'mac': 'd8:07:b6:aa:0f:29'},
    {'name': 'hs103-89', 'mac': 'd8:07:b6:a9:f6:89'},
    {'name': 'hs1032d', 'mac': 'd8:07:b6:aa:01:2d'},
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
