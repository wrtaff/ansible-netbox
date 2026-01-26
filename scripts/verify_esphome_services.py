#!/usr/bin/env python3
import os
import requests
import sys

NETBOX_URL = "http://netbox1.home.arpa"
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN")

if not NETBOX_TOKEN:
    print("Error: NETBOX_TOKEN environment variable not set.")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Token {NETBOX_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

SERVICE_NAME = "IoT - Device Management (ESPHome)"
PORT = 80
PROTOCOL = "tcp"

def get_esphome_devices():
    """Fetch all devices with Platform ID 8 (ESPHome)."""
    url = f"{NETBOX_URL}/api/dcim/devices/?platform_id=8&limit=0"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json().get('results', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching devices: {e}")
        return []

def check_connectivity(ip_address):
    """Check if the device has a web interface on port 80."""
    if not ip_address:
        return False
    
    # Strip CIDR if present
    clean_ip = ip_address.split('/')[0]
    target_url = f"http://{clean_ip}"
    
    print(f"Checking connectivity to {target_url} ... ", end='', flush=True)
    try:
        requests.get(target_url, timeout=2)
        print("Success.")
        return True
    except requests.exceptions.RequestException:
        print("Failed.")
        return False

def get_device_services(device_id):
    """Fetch services attached to a device."""
    url = f"{NETBOX_URL}/api/ipam/services/?device_id={device_id}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json().get('results', [])
    except requests.exceptions.RequestException as e:
        print(f"Error fetching services for device {device_id}: {e}")
        return []

def create_service(device_id, ip_address):
    """Create the standardized service."""
    clean_ip = ip_address.split('/')[0]
    payload = {
        "device": device_id,
        "name": SERVICE_NAME,
        "protocol": PROTOCOL,
        "ports": [PORT],
        "description": "ESPHome Web Interface",
        "comments": f"[ESPHome Web Interface](http://{clean_ip})"
    }
    
    url = f"{NETBOX_URL}/api/ipam/services/"
    try:
        response = requests.post(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        print(f"  + Created service '{SERVICE_NAME}' for device {device_id}.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  ! Error creating service: {e}")
        if hasattr(e, 'response') and e.response is not None:
             print(f"    Response: {e.response.text}")
        return None

def update_service(service_id, ip_address):
    """Update existing service to match standards."""
    clean_ip = ip_address.split('/')[0]
    payload = {
        "name": SERVICE_NAME,
        "comments": f"[ESPHome Web Interface](http://{clean_ip})"
    }
    
    url = f"{NETBOX_URL}/api/ipam/services/{service_id}/"
    try:
        response = requests.patch(url, headers=HEADERS, json=payload)
        response.raise_for_status()
        print(f"  * Updated service {service_id} to match standards.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  ! Error updating service: {e}")
        return None

def process_device(device):
    name = device.get('name')
    device_id = device.get('id')
    primary_ip_obj = device.get('primary_ip')
    
    print(f"[{name}] (ID: {device_id})")
    
    if not primary_ip_obj:
        print("  ! No primary IP assigned. Skipping.")
        return

    primary_ip = primary_ip_obj.get('address')
    
    # 1. Verify Connectivity
    if not check_connectivity(primary_ip):
        print("  ! Web interface unreachable. Skipping documentation updates.")
        return

    # 2. Check Existing Services
    services = get_device_services(device_id)
    target_service = None
    
    # Find existing service on port 80
    for service in services:
        if 80 in service.get('ports', []):
            target_service = service
            break
            
    if target_service:
        # Check if update needed
        current_name = target_service.get('name')
        current_comment = target_service.get('comments', '')
        expected_comment = f"[ESPHome Web Interface](http://{primary_ip.split('/')[0]})"
        
        if current_name != SERVICE_NAME or expected_comment not in current_comment:
            print(f"  * Found non-compliant service: '{current_name}'. Updating...")
            update_service(target_service['id'], primary_ip)
        else:
            print("  = Service already compliant.")
    else:
        # Create new service
        print("  + No service found on port 80. Creating...")
        create_service(device_id, primary_ip)
        
    print("-" * 40)

def main():
    print("Starting ESPHome Service Verification...")
    devices = get_esphome_devices()
    print(f"Found {len(devices)} ESPHome devices.")
    print("-" * 40)
    
    for device in devices:
        process_device(device)

if __name__ == "__main__":
    main()
