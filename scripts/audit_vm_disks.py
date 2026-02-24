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
        print(f"Patched VM {vm_id} successfully.")
    else:
        print(f"Failed to patch VM {vm_id}: {response.text}")

def create_disk(vm_id, name, size_mb, description=""):
    url = f"{NETBOX_URL}/virtualization/virtual-disks/"
    data = {
        "virtual_machine": vm_id,
        "name": name,
        "size": size_mb,
        "description": description
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 201:
        print(f"Created disk for VM {vm_id} successfully.")
    else:
        print(f"Failed to create disk for VM {vm_id}: {response.text}")

# Host Association Updates
host_updates = [
    (11, 10), # ansible-ctl -> proxmox1
    (2, 10),  # apollo -> proxmox1
    (10, 10), # homeassistant -> proxmox1
    (6, 10),  # mne-server -> proxmox1
    (9, 10),  # mw2-pve -> proxmox1
    (1, 10),  # netbox1 -> proxmox1
    (13, 10), # wazuh-siem -> proxmox1
    (27, 13), # caddy01 -> pve2
    (20, 13), # graylog -> pve2
    (24, 13), # vik-01 -> pve2
]

for vm_id, device_id in host_updates:
    patch_vm(vm_id, {"device": device_id})

# Disk Creation Updates
disk_updates = [
    (11, 8000),   # ansible-ctl
    (15, 8000),   # unifi
    (16, 10000),  # paperless-ngx
    (21, 10000),  # pihole-primary
    (14, 10000),  # tandoor
    (23, 8000),   # trac-lxc
]

for vm_id, size in disk_updates:
    create_disk(vm_id, "rootfs", size, "Primary root filesystem")

# Special case for vik-01 where I suspect 16 was meant to be 16GB
create_disk(24, "rootfs", 16384, "Primary root filesystem (Assumed 16GB)")
