#!/usr/bin/env python3
import os
import requests
import json
import sys
import subprocess

# Configuration
# Default to http://hass.home.arpa if not set.
HASS_URL = os.getenv("HASS_URL", "http://hass.home.arpa")

# Token can be set via environment variable. 
# If not set, the script will attempt to retrieve it from vault.yml.
# FUTURE: Remember to make a temporary copy of the api key so you don't have to keep asking me for the vault password in a session.
HASS_TOKEN = os.getenv("HASS_TOKEN")

def get_token_from_tmp():
    """Attempts to retrieve the hass_token from a temporary file."""
    # Check for a temp token file to avoid repeated vault prompts
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tmp_token_file = os.path.join(script_dir, "..", "tmp", "hass_token.txt")
    
    if os.path.exists(tmp_token_file):
        try:
            with open(tmp_token_file, 'r') as f:
                return f.read().strip()
        except Exception:
            pass
    return None

def get_token_from_vault():
    """Attempts to retrieve the hass_token from vault.yml using ansible-vault."""
    # Assume vault.yml is in the parent directory of the script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    vault_file = os.path.join(script_dir, "..", "vault.yml")
    
    if not os.path.exists(vault_file):
        return None
    
    try:
        # This requires ansible-vault to be able to decrypt the file 
        # (e.g., via ANSIBLE_VAULT_PASSWORD_FILE or if the password is not required/cached)
        result = subprocess.run(
            ["ansible-vault", "view", vault_file],
            capture_output=True,
            text=True,
            check=True
        )
        for line in result.stdout.splitlines():
            if "hass_gemini_api_key:" in line:
                # Extract value after the colon and strip quotes
                token = line.split(":", 1)[1].strip().strip("'").strip('"')
                return token
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fail silently if vault cannot be read
        pass
    except Exception as e:
        print(f"DEBUG: Vault retrieval error: {e}", file=sys.stderr)
        
    return None

def get_headers():
    global HASS_TOKEN
    
    # Try to get from vault if not already set
    if not HASS_TOKEN:
        HASS_TOKEN = get_token_from_tmp()

    if not HASS_TOKEN:
        HASS_TOKEN = get_token_from_vault()
        # Save the token to the temp file if it was retrieved from the vault
        if HASS_TOKEN:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            tmp_token_file = os.path.join(script_dir, "..", "tmp", "hass_token.txt")
            try:
                os.makedirs(os.path.dirname(tmp_token_file), exist_ok=True)
                with open(tmp_token_file, 'w') as f:
                    f.write(HASS_TOKEN)
                # Set permissions to read/write for owner only
                os.chmod(tmp_token_file, 0o600)
            except Exception as e:
                print(f"DEBUG: Could not save temp token: {e}", file=sys.stderr)
        
    if not HASS_TOKEN:
        print("Error: HASS_TOKEN environment variable is not set and could not be retrieved from vault.yml.")
        print("\nTo resolve this, you can:")
        print("1. Set the environment variable directly:")
        print("   export HASS_TOKEN='your_long_lived_access_token'")
        print("\n2. Provide the vault password so the script can read it from vault.yml:")
        print("   export ANSIBLE_VAULT_PASSWORD_FILE=~/.vault_pass.txt")
        print("\n3. Manually extract it (if you know the vault password):")
        print("   export HASS_TOKEN=$(ansible-vault view vault.yml | grep hass_token | awk '{print $2}' | tr -d '\"' | tr -d \"'\")")
        sys.exit(1)
    
    return {
        "Authorization": f"Bearer {HASS_TOKEN}",
        "Content-Type": "application/json",
    }

def check_api_status():
    """Checks if the API is running."""
    url = f"{HASS_URL}/api/"
    try:
        print(f"Checking API status at {url}...")
        response = requests.get(url, headers=get_headers(), timeout=5)
        response.raise_for_status()
        print(f"API Status: {response.json().get('message', 'OK')}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error checking API status: {e}")
        return False

def get_state(entity_id):
    """Retrieves state for a specific entity."""
    url = f"{HASS_URL}/api/states/{entity_id}"
    try:
        response = requests.get(url, headers=get_headers(), timeout=5)
        response.raise_for_status()
        state = response.json()
        print(json.dumps(state, indent=2))
        return state
    except requests.exceptions.RequestException as e:
        print(f"Error getting state for {entity_id}: {e}")
        return None

def get_all_states():
    """Retrieves all states."""
    url = f"{HASS_URL}/api/states"
    try:
        response = requests.get(url, headers=get_headers(), timeout=5)
        response.raise_for_status()
        states = response.json()
        print(f"Retrieved {len(states)} states.")
        return states
    except requests.exceptions.RequestException as e:
        print(f"Error getting states: {e}")
        return []

def call_service(domain, service, service_data):
    """Calls a service."""
    url = f"{HASS_URL}/api/services/{domain}/{service}"
    try:
        print(f"Calling service {domain}.{service} with data: {service_data}")
        response = requests.post(url, headers=get_headers(), json=service_data, timeout=5)
        response.raise_for_status()
        print("Service call successful.")
        print(json.dumps(response.json(), indent=2))
    except requests.exceptions.RequestException as e:
        print(f"Error calling service: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: ./hass_api_manager.py <command> [args]")
        print("Commands:")
        print("  status              - Check API status")
        print("  states              - List all states (summary)")
        print("  state <entity_id>   - Get full state of an entity")
        print("  on <entity_id>      - Turn on a light/switch")
        print("  off <entity_id>     - Turn off a light/switch")
        print("  call <domain> <service> <json_data> - Generic service call")
        sys.exit(1)

    command = sys.argv[1]

    if command == "status":
        check_api_status()
    elif command == "states":
        states = get_all_states()
        for s in states:
            print(f"{s['entity_id']}: {s['state']}")
    elif command == "state":
        if len(sys.argv) < 3:
            print("Usage: ./hass_api_manager.py state <entity_id>")
            sys.exit(1)
        get_state(sys.argv[2])
    elif command == "on":
        if len(sys.argv) < 3:
            print("Usage: ./hass_api_manager.py on <entity_id>")
            sys.exit(1)
        call_service("homeassistant", "turn_on", {"entity_id": sys.argv[2]})
    elif command == "off":
        if len(sys.argv) < 3:
            print("Usage: ./hass_api_manager.py off <entity_id>")
            sys.exit(1)
        call_service("homeassistant", "turn_off", {"entity_id": sys.argv[2]})
    elif command == "call":
        if len(sys.argv) < 5:
            print("Usage: ./hass_api_manager.py call <domain> <service> <json_data>")
            sys.exit(1)
        domain = sys.argv[2]
        service = sys.argv[3]
        try:
            data = json.loads(sys.argv[4])
        except json.JSONDecodeError:
            print("Error: Invalid JSON data")
            sys.exit(1)
        call_service(domain, service, data)
    elif command == "dump":
        states = get_all_states()
        print(json.dumps(states, indent=2))
    else:
        print(f"Unknown command: {command}")
