import os
import requests
import json
import sys

NETBOX_URL = 'http://netbox1.home.arpa/api'
TOKEN = os.environ.get('NETBOX_TOKEN', '')
if not TOKEN:
    # Just in case it's not set in env, let's grab it from ~/.bashrc or similar.
    # But usually it's in env.
    pass

headers = {
    'Authorization': f'Token {TOKEN}',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

def get_or_create_manufacturer(name, slug):
    r = requests.get(f'{NETBOX_URL}/dcim/manufacturers/?slug={slug}', headers=headers)
    res = r.json()
    if res['count'] > 0:
        return res['results'][0]['id']
    
    r = requests.post(f'{NETBOX_URL}/dcim/manufacturers/', headers=headers, json={'name': name, 'slug': slug})
    if r.status_code == 201:
        return r.json()['id']
    else:
        print("Failed to create manufacturer:", r.text)
        sys.exit(1)

def get_or_create_device_type(model, slug, mfg_id):
    r = requests.get(f'{NETBOX_URL}/dcim/device-types/?slug={slug}', headers=headers)
    res = r.json()
    if res['count'] > 0:
        return res['results'][0]['id']
    
    data = {
        'manufacturer': mfg_id,
        'model': model,
        'slug': slug,
        'u_height': 0,
        'is_full_depth': False
    }
    r = requests.post(f'{NETBOX_URL}/dcim/device-types/', headers=headers, json=data)
    if r.status_code == 201:
        return r.json()['id']
    else:
        print("Failed to create device type:", r.text)
        sys.exit(1)

def get_or_create_device_role(name, slug):
    r = requests.get(f'{NETBOX_URL}/dcim/device-roles/?slug={slug}', headers=headers)
    res = r.json()
    if res['count'] > 0:
        return res['results'][0]['id']
    
    r = requests.post(f'{NETBOX_URL}/dcim/device-roles/', headers=headers, json={'name': name, 'slug': slug, 'color': '9e9e9e'})
    if r.status_code == 201:
        return r.json()['id']
    else:
        print("Failed to create device role:", r.text)
        sys.exit(1)

def get_site_id():
    r = requests.get(f'{NETBOX_URL}/dcim/sites/?slug=taff-csg-ga-01', headers=headers)
    res = r.json()
    if res['count'] > 0:
        return res['results'][0]['id']
    return 1 # Fallback

def get_location_id():
    r = requests.get(f'{NETBOX_URL}/dcim/locations/?slug=master-bedroom', headers=headers)
    res = r.json()
    if res['count'] > 0:
        return res['results'][0]['id']
    return None

def create_device(name, device_type_id, role_id, site_id, loc_id):
    r = requests.get(f'{NETBOX_URL}/dcim/devices/?name={name}', headers=headers)
    res = r.json()
    if res['count'] > 0:
        return res['results'][0]['id']
    
    data = {
        'name': name,
        'device_type': device_type_id,
        'role': role_id,
        'site': site_id,
        'location': loc_id,
        'status': 'active'
    }
    r = requests.post(f'{NETBOX_URL}/dcim/devices/', headers=headers, json=data)
    if r.status_code == 201:
        return r.json()['id']
    else:
        print("Failed to create device:", r.text)
        sys.exit(1)

def ensure_interface(device_id, name, type_val):
    r = requests.get(f'{NETBOX_URL}/dcim/interfaces/?device_id={device_id}&name={name}', headers=headers)
    res = r.json()
    if res['count'] > 0:
        return res['results'][0]['id']
    
    data = {
        'device': device_id,
        'name': name,
        'type': type_val
    }
    r = requests.post(f'{NETBOX_URL}/dcim/interfaces/', headers=headers, json=data)
    if r.status_code == 201:
        return r.json()['id']
    else:
        print("Failed to create interface:", r.text)
        sys.exit(1)

def cable_interfaces(iface_a, iface_b):
    # check if already cabled
    r = requests.get(f'{NETBOX_URL}/dcim/cables/?interfaces={iface_a}', headers=headers)
    if r.json()['count'] > 0:
        print("Interface A already cabled")
        return
    
    data = {
        'a_terminations': [{'object_type': 'dcim.interface', 'object_id': iface_a}],
        'b_terminations': [{'object_type': 'dcim.interface', 'object_id': iface_b}],
        'status': 'connected'
    }
    r = requests.post(f'{NETBOX_URL}/dcim/cables/', headers=headers, json=data)
    if r.status_code == 201:
        print("Cable created successfully")
    else:
        print("Failed to create cable:", r.text)

if __name__ == '__main__':
    # Try to load token from ~/.bashrc if empty
    if not TOKEN:
        with open(os.path.expanduser('~/.bashrc')) as f:
            for line in f:
                if 'NETBOX_TOKEN' in line:
                    TOKEN = line.split('=')[1].strip().strip('"').strip("'")
                    headers['Authorization'] = f'Token {TOKEN}'
                    break

    mfg_id = get_or_create_manufacturer('Brother', 'brother')
    dt_id = get_or_create_device_type('ADS-2000', 'ads-2000', mfg_id)
    role_id = get_or_create_device_role('Scanner', 'scanner')
    site_id = get_site_id()
    loc_id = get_location_id()
    
    dev_id = create_device('brother-ads-2000', dt_id, role_id, site_id, loc_id)
    print(f"Scanner device ID: {dev_id}")
    
    scanner_iface = ensure_interface(dev_id, 'usb-uplink', 'other')
    print(f"Scanner Interface ID: {scanner_iface}")
    
    # User said: "create the device in netbox at http://netbox1.home.arpa/dcim/interfaces/449/"
    hub_iface_id = 449
    
    cable_interfaces(scanner_iface, hub_iface_id)
    print("Done setting up NetBox.")
