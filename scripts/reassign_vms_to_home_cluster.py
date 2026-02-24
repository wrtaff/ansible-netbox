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

# List of VMs to move from cluster 4 to cluster 6 and associate with pve2 (13)
vms_to_move = [
    27, # caddy01
    20, # graylog
    24, # vik-01
    17, # gmailctl-ansible (already in cluster 4, has host pve2 but patch failed?)
    18, # n8n
    26, # ot-recorder
    16, # paperless-ngx
    19, # pbs01
    21, # pihole-primary
    14, # tandoor
    23, # trac-lxc
]

for vm_id in vms_to_move:
    patch_vm(vm_id, {"cluster": 6, "device": 13})

# Ensure disks are created if they were missed or if I suspect size issues
# VM 24 (vik-01) already created in previous run but maybe I should check others
# I'll just skip the ones I already did successfully in previous run.
# Actually I'll just run it once for the missed ones.
