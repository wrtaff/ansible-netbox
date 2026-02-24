import os
import requests
import json

NETBOX_URL = "http://netbox1.home.arpa/api"
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN")

headers = {
    "Authorization": f"Token {NETBOX_TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

def patch_vm(vm_id, data):
    url = f"{NETBOX_URL}/virtualization/virtual-machines/{vm_id}/"
    response = requests.patch(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"Patched VM {vm_id} ({data.get('name', 'unnamed')}) successfully.")
    else:
        print(f"Failed to patch VM {vm_id}: {response.text}")

def create_or_update_disk(vm_id, name, size_mb, description=""):
    # Check if disk exists
    url = f"{NETBOX_URL}/virtualization/virtual-disks/?virtual_machine_id={vm_id}&name={name}"
    response = requests.get(url, headers=headers)
    results = response.json().get('results', [])
    
    if results:
        disk_id = results[0]['id']
        url = f"{NETBOX_URL}/virtualization/virtual-disks/{disk_id}/"
        data = {"size": size_mb, "description": description}
        response = requests.patch(url, headers=headers, json=data)
        print(f"Updated disk {disk_id} for VM {vm_id}.")
    else:
        url = f"{NETBOX_URL}/virtualization/virtual-disks/"
        data = {
            "virtual_machine": vm_id,
            "name": name,
            "size": size_mb,
            "description": description
        }
        response = requests.post(url, headers=headers, json=data)
        print(f"Created disk for VM {vm_id}.")

# VM ID mapping and data
# Hosts: 10 (proxmox1), 13 (pve2)
# Cluster: 1 (hestia), 6 (home-cluster/pve2)

updates = [
    # Proxmox1 (Hestia) - Cluster 1
    {"id": 1, "host": 10, "cluster": 1, "disk": 18432, "name": "netbox1"},
    {"id": 6, "host": 10, "cluster": 1, "disk": 4096, "name": "mne-server"},
    {"id": 9, "host": 10, "cluster": 1, "disk": 20480, "name": "mw2-pve"},
    {"id": 13, "host": 10, "cluster": 1, "disk": 30720, "name": "wazuh-siem"},
    {"id": 15, "host": 10, "cluster": 1, "disk": 8192, "name": "unifi"},
    {"id": 10, "host": 10, "cluster": 1, "disk": 32768, "name": "homeassistant"},
    {"id": 4, "host": 10, "cluster": 1, "disk": 71680, "name": "ynh2"},

    # PVE2 (Z420) - Cluster 6
    {"id": 20, "host": 13, "cluster": 6, "disk": 30720, "name": "graylog"},
    {"id": 16, "host": 13, "cluster": 6, "disk": 10240, "name": "paperless-ngx"},
    {"id": 18, "host": 13, "cluster": 6, "disk": 10240, "name": "n8n"},
    {"id": 17, "host": 13, "cluster": 6, "disk": 4096, "name": "gmailctl-ansible"},
    {"id": 19, "host": 13, "cluster": 6, "disk": 10240, "name": "pbs01"},
    {"id": 21, "host": 13, "cluster": 6, "disk": 5120, "name": "pihole-primary"},
    {"id": 23, "host": 13, "cluster": 6, "disk": 8192, "name": "trac-lxc"},
    {"id": 24, "host": 13, "cluster": 6, "disk": 16384, "name": "vik-01"},
    {"id": 14, "host": 13, "cluster": 6, "disk": 10240, "name": "tandoor"},
    {"id": 26, "host": 13, "cluster": 6, "disk": 4096, "name": "ot-recorder"},
    {"id": 27, "host": 13, "cluster": 6, "disk": 4096, "name": "caddy01"},
]

for up in updates:
    patch_vm(up['id'], {"device": up['host'], "cluster": up['cluster']})
    create_or_update_disk(up['id'], "rootfs", up['disk'], "Primary root filesystem")
