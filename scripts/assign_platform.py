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
    'hs103-a3',
    'hs103-a929',
    'HS103',
    'hs103-29',
    'hs103-89',
    'hs103-dc',
    'hs1032d',
    'hs200-1',
    'hs200-2',
]

platform_id = 18

def get_device_id_by_name(device_name):
    url = f"{NETBOX_URL}/api/dcim/devices/?name={device_name}"
    response = requests.get(url, headers=HEADERS, verify=False)
    response.raise_for_status()
    devices = response.json().get('results')
    if devices:
        return devices[0]['id']
    return None

def set_platform(device_id, platform_id):
    device_data = {
        "platform": {"id": platform_id}
    }
    url = f"{NETBOX_URL}/api/dcim/devices/{device_id}/"
    response = requests.patch(url, headers=HEADERS, json=device_data, verify=False)
    response.raise_for_status()
    return response.json()

def main():
    for device_name in devices_to_update:
        print(f"Setting platform for {device_name}...")
        
        try:
            device_id = get_device_id_by_name(device_name)
            if not device_id:
                print(f"Device {device_name} not found in NetBox. Skipping.")
                continue

            print(f"Found device: {device_name} (ID: {device_id})")

            netbox_device = set_platform(device_id, platform_id)
            print(f"Successfully set platform for {device_name}.")

        except requests.exceptions.RequestException as e:
            print(f"Error setting platform for {device_name}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response content: {e.response.text}")
        print("-" * 30)

if __name__ == "__main__":
    main()
