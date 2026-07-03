#!/usr/bin/env python3
import json
import urllib.request
import sys
import os

def get_hass_token():
    token = os.environ.get('HASS_TOKEN')
    if token:
        return token
    
    config_path = '/home/will/pops/.mcp.json'
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get('mcpServers', {}).get('homeassistant', {}).get('env', {}).get('HASS_TOKEN')
    except Exception as e:
        print(f"Error reading token from {config_path}: {e}", file=sys.stderr)
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: hass_api.py <endpoint_path> [method] [json_body]", file=sys.stderr)
        print("Example: hass_api.py /api/states/plant.corn_plant", file=sys.stderr)
        sys.exit(1)
        
    endpoint = sys.argv[1]
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
        
    method = sys.argv[2].upper() if len(sys.argv) > 2 else "GET"
    body = sys.argv[3] if len(sys.argv) > 3 else None
    
    token = get_hass_token()
    if not token:
        print("Failed to find HASS_TOKEN in ~/.mcp.json", file=sys.stderr)
        sys.exit(1)
        
    url = f"http://hass.home.arpa{endpoint}"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    data = body.encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            print(json.dumps(result, indent=2))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
