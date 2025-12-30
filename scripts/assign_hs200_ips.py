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

devices_to_provision = [
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

def get_device_interface(device_id):
    url = f"{NETBOX_URL}/api/dcim/interfaces/?device_id={device_id}&name=WiFi"
    response = requests.get(url, headers=HEADERS, verify=False)
    response.raise_for_status()
    interfaces = response.json().get('results')
    if interfaces:
        return interfaces[0]['id']
    return None

def assign_ip_to_interface(ip_address, interface_id):
    ip_data = {
        "address": ip_address,
        "status": "active",
        "assigned_object_type": "dcim.interface",
        "assigned_object_id": interface_id
    }
    url = f"{NETBOX_URL}/api/ipam/ip-addresses/"
    response = requests.post(url, headers=HEADERS, json=ip_data, verify=False)
    response.raise_for_status()
    return response.json()

def get_device_ip(device_id):
    url = f"{NETBOX_URL}/api/ipam/ip-addresses/?device_id={device_id}"
    response = requests.get(url, headers=HEADERS, verify=False)
    response.raise_for_status()
    ips = response.json().get('results')
    if ips:
        return ips[0]['address']
    return None

def main():
    for device in devices_to_provision:
        device_name = device['name']
        ip_address = device['ip']
        
        print(f"Assigning IP {ip_address} to {device_name}...")
        
        try:
            device_id = get_device_id_by_name(device_name)
            if not device_id:
                print(f"Device {device_name} not found in NetBox. Skipping IP assignment.")
                continue

            print(f"Found device: {device_name} (ID: {device_id})")
            
            interface_id = get_device_interface(device_id)
            if interface_id:
                print(f"Found WiFi interface ID: {interface_id}")
                netbox_ip = assign_ip_to_interface(ip_address, interface_id)
                print(f"Assigned IP {netbox_ip['address']} (ID: {netbox_ip['id']}) to interface.")

                # Verify IP was assigned
                assigned_ip = get_device_ip(device_id)
                if assigned_ip:
                    print(f"Verification successful: Found IP {assigned_ip} for device {device_name}")
                else:
                    print(f"Verification failed: Could not find IP for device {device_name}")

            else:
                print(f"Could not find WiFi interface for device {device_name}. Skipping IP assignment.")
                
        except requests.exceptions.RequestException as e:
            print(f"Error assigning IP to {device_name}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
        print("-" * 30)

if __name__ == "__main__":
    main()
