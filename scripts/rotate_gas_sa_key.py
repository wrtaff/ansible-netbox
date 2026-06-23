#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/rotate_gas_sa_key.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-06-22
Context:        http://trac.home.arpa/ticket/3205

Purpose:
    Automates the zero-downtime rotation of Google Apps Script (GAS) service account keys.
    Lists existing keys, generates a new key, pauses for deployment, then deletes old keys.

Usage:
    python3 scripts/rotate_gas_sa_key.py <project_id> <service_account_email>

Revision History:
    v1.0 (2026-06-22): Initial version

Secrets:
    None — no credentials or secrets required
================================================================================
"""

import sys
import os
import json
import subprocess

def run_gcp_manager(args):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gcp_manager_path = os.path.join(script_dir, 'gcp_manager.py')
    cmd = [sys.executable, gcp_manager_path] + args
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout, result.stderr, result.returncode

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 rotate_gas_sa_key.py <project_id> <service_account_email>")
        sys.exit(1)
        
    project_id = sys.argv[1]
    email = sys.argv[2]
    
    print(f"=== Starting Zero-Downtime Key Rotation ===")
    print(f"Project: {project_id}")
    print(f"Service Account: {email}\n")
    
    print("1. Fetching current keys...")
    stdout, stderr, code = run_gcp_manager(['list-keys', project_id, email])
    if code != 0:
        print(f"Failed to list keys:\n{stdout}\n{stderr}")
        sys.exit(1)
        
    # parse the json output (may contain HTTP Error lines, so grab from '[' )
    try:
        json_str = stdout[stdout.index('['):]
        keys = json.loads(json_str)
    except Exception as e:
        print("Failed to parse existing keys.")
        print(stdout)
        sys.exit(1)
        
    user_keys = [k for k in keys if k.get('keyType') == 'USER_MANAGED']
    if not user_keys:
        print("No USER_MANAGED keys found. Proceeding to create the first one.")
    else:
        print("Existing USER_MANAGED keys:")
        for k in user_keys:
            key_id = k['name'].split('/')[-1]
            print(f"  - {key_id} (Valid after: {k.get('validAfterTime')})")
            
    print("\n2. Generating new key...")
    stdout, stderr, code = run_gcp_manager(['create-key', project_id, email])
    if code != 0:
        print(f"Failed to create key:\n{stdout}\n{stderr}")
        sys.exit(1)
        
    try:
        json_str = stdout[stdout.index('{'):]
        new_key_data = json.loads(json_str)
        new_key_id = new_key_data['name'].split('/')[-1]
    except Exception as e:
        print("Failed to parse new key output.")
        print(stdout)
        sys.exit(1)
        
    print(f"✅ Successfully created new key: {new_key_id}")
    print("\n=======================================================")
    print("NEW KEY DATA (Copy this and deploy to GAS Script Properties):")
    print("=======================================================")
    print(json_str)
    print("=======================================================\n")
    
    if not user_keys:
        print("No old keys to delete. Rotation complete.")
        sys.exit(0)
        
    print("3. Pausing for deployment...")
    response = input("Have you successfully deployed the new key to GAS and verified it works? (y/N): ")
    if response.lower() != 'y':
        print("Aborting old key deletion. The new key remains active.")
        print("Please delete the old keys manually when ready.")
        sys.exit(0)
        
    print("\n4. Deleting old keys...")
    for k in user_keys:
        old_key_id = k['name'].split('/')[-1]
        print(f"Deleting key {old_key_id}...")
        stdout, stderr, code = run_gcp_manager(['delete-key', project_id, email, old_key_id])
        if code != 0:
            print(f"Failed to delete {old_key_id}:\n{stdout}\n{stderr}")
        else:
            print(f"✅ Successfully deleted old key: {old_key_id}")
            
    print("\n=== Rotation Complete ===")
    print(f"Remember to log this rotation in the Trac key management ticket.")

if __name__ == "__main__":
    main()
