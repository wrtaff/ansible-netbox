#!/bin/bash
cd /home/will/ansible-netbox

# No need to specify password file if ansible.cfg has vault_password_file = ~/.vault_pass
# But wait, earlier I decrypted it with it.
ansible-vault encrypt vault.yml
