#!/usr/bin/env python3
"""
================================================================================
Filename:       wazuh_query.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-07-24
Purpose:        Query the Wazuh API (https://192.168.0.11:55000) for agents list,
                summary, health, and arbitrary endpoints.
================================================================================
"""
import argparse
import urllib.request
import json
import ssl
import base64
import sys

WAZUH_HOST = '192.168.0.11'
WAZUH_PORT = 55000
WAZUH_USER = 'wazuh-wui'
WAZUH_PASS = 'WazuhWui2026!'

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def get_token(ctx):
    url = f'https://{WAZUH_HOST}:{WAZUH_PORT}/security/user/authenticate'
    req = urllib.request.Request(url, method='POST')
    auth_str = f'{WAZUH_USER}:{WAZUH_PASS}'
    base64_string = base64.b64encode(auth_str.encode('ascii')).decode('ascii')
    req.add_header("Authorization", f"Basic {base64_string}")
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            res = json.loads(response.read())
            return res['data']['token']
    except Exception as e:
        print(f"Authentication failed: {e}", file=sys.stderr)
        sys.exit(1)

def make_request(endpoint, token, ctx, method='GET', data=None):
    url = f'https://{WAZUH_HOST}:{WAZUH_PORT}/{endpoint.lstrip("/")}'
    req = urllib.request.Request(url, method=method)
    req.add_header('Authorization', f'Bearer {token}')
    if data:
        req.add_header('Content-Type', 'application/json')
        req.data = json.dumps(data).encode('utf-8')
        
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            return json.loads(response.read())
    except Exception as e:
        print(f"Request to {endpoint} failed: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Query Wazuh API")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Agents subcommand
    agents_parser = subparsers.add_parser('agents', help='List agents')
    agents_parser.add_argument('--limit', type=int, default=10, help='Maximum number of agents to return')
    
    # Summary subcommand
    subparsers.add_parser('summary', help='Get agents status summary')
    
    # Raw subcommand
    raw_parser = subparsers.add_parser('raw', help='Query arbitrary endpoint')
    raw_parser.add_argument('endpoint', type=str, help='API endpoint (e.g. agents/001/syscheck)')
    
    args = parser.parse_args()
    
    ctx = get_ssl_context()
    token = get_token(ctx)
    
    if args.command == 'agents':
        endpoint = f'agents?select=id,name,status,ip,version&limit={args.limit}'
        res = make_request(endpoint, token, ctx)
        print(json.dumps(res, indent=2))
        
    elif args.command == 'summary':
        res = make_request('agents/summary', token, ctx)
        print(json.dumps(res, indent=2))
        
    elif args.command == 'raw':
        res = make_request(args.endpoint, token, ctx)
        print(json.dumps(res, indent=2))

if __name__ == '__main__':
    main()
