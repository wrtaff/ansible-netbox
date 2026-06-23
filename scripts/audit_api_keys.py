import sys
import json
import pickle
import os.path
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

TOKEN_FILE = os.path.expanduser('~/ansible-netbox/scripts/token.pickle')

def get_creds():
    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds

def main():
    creds = get_creds()
    rm_service = build('cloudresourcemanager', 'v1', credentials=creds)
    try:
        projects = rm_service.projects().list().execute().get('projects', [])
    except Exception as e:
        print("Failed to list projects:", e)
        return
        
    for p in projects:
        pid = p['projectId']
        print(f"=== Project: {pid} ===")
        try:
            pid_creds = creds.with_quota_project(pid)
            apikeys_service = build('apikeys', 'v2', credentials=pid_creds)
            parent = f"projects/{pid}/locations/global"
            request = apikeys_service.projects().locations().keys().list(parent=parent)
            response = request.execute()
            keys = response.get('keys', [])
            if not keys:
                # No keys found
                pass
            for key in keys:
                name = key.get('name')
                display_name = key.get('displayName', 'Unnamed Key')
                restrictions = key.get('restrictions', {})
                print(f"  Key: {display_name} ({name})")
                
                # Check restrictions
                browser_key_restrictions = restrictions.get('browserKeyRestrictions')
                server_key_restrictions = restrictions.get('serverKeyRestrictions')
                android_key_restrictions = restrictions.get('androidKeyRestrictions')
                ios_key_restrictions = restrictions.get('iosKeyRestrictions')
                api_targets = restrictions.get('apiTargets')
                
                has_env = any([browser_key_restrictions, server_key_restrictions, android_key_restrictions, ios_key_restrictions])
                if not has_env:
                    print("    [WARNING] No Environmental (IP/HTTP/App) restrictions!")
                else:
                    if browser_key_restrictions:
                        print("    - Environmental: HTTP Referrers restricted")
                    if server_key_restrictions:
                        print("    - Environmental: IP restricted")
                    if android_key_restrictions:
                        print("    - Environmental: Android apps restricted")
                    if ios_key_restrictions:
                        print("    - Environmental: iOS apps restricted")
                
                if not api_targets:
                    print("    [WARNING] No API-specific restrictions! Key can access any enabled API.")
                else:
                    targets = [t.get('service') for t in api_targets]
                    print(f"    - API Restricted to: {', '.join(targets)}")
                    
        except HttpError as e:
            if e.resp.status == 403 and 'has not been used' in str(e):
                # API Keys API is disabled on this project, safely assume no keys.
                pass 
            else:
                print(f"  HTTP Error: {e.reason}")
        except Exception as e:
            print(f"  Error: {e}")

if __name__ == '__main__':
    main()
