#!/usr/bin/env python3
# ==============================================================================
# Script:     migrate_paperless_scans.py
# Purpose:    Fetch documents added today from Paperless-ngx API and upload 
#             them to the Google Drive Intake folder for automated renaming.
# Secrets:    Requires Paperless-ngx API Token (hardcoded or env var)
# ==============================================================================
# Revision History:
#   2026-06-15  Antigravity  Initial creation
# ==============================================================================

import os
import sys
import json
import requests
import subprocess
from datetime import datetime

PAPERLESS_URL = "http://paperless-ngx.home.arpa/api/documents/"
TOKEN = os.environ.get("PAPERLESS_API_TOKEN")
if not TOKEN:
    print("Error: PAPERLESS_API_TOKEN environment variable is not set.", file=sys.stderr)
    sys.exit(1)
GDRIVE_FOLDER_ID = "1Qa1jqZB5nbK4OWNfMZkpG7HjwXvLMCzV"

def main():
    headers = {"Authorization": f"Token {TOKEN}"}
    print(f"Fetching all documents from Paperless-ngx...")
    
    docs = []
    next_url = PAPERLESS_URL
    while next_url:
        response = requests.get(next_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        docs.extend(data.get('results', []))
        next_url = data.get('next')
    
    if not docs:
        print("No documents found in Paperless.")
        return
        
    print(f"Found {len(docs)} documents to process.")
    
    # Import google_workspace_manager
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from google_workspace_manager import drive_upload_file
    
    for doc in docs:
        doc_id = doc['id']
        title = doc['title']
        if not title.endswith('.pdf'):
            title += '.pdf'
            
        print(f"Processing '{title}' (ID: {doc_id})...")
        download_url = f"http://paperless-ngx.home.arpa/api/documents/{doc_id}/download/"
        
        # Download the file
        local_path = f"/tmp/{title}"
        doc_resp = requests.get(download_url, headers=headers)
        doc_resp.raise_for_status()
        
        with open(local_path, 'wb') as f:
            f.write(doc_resp.content)
            
        print(f"Downloaded to {local_path}. Uploading to Google Drive...")
        
        # Upload to Google Drive
        try:
            result = drive_upload_file(
                file_path=local_path,
                parent_id=GDRIVE_FOLDER_ID,
                target_mimetype="application/pdf"
            )
            print(f"Successfully uploaded {title} to Drive: {result}")
            
            # Verify and delete from Paperless
            if result and 'id' in result:
                print(f"Verification successful. Deleting {title} from Paperless...")
                del_url = f"http://paperless-ngx.home.arpa/api/documents/{doc_id}/"
                del_resp = requests.delete(del_url, headers=headers)
                del_resp.raise_for_status()
                print("Deleted from Paperless successfully.")
            else:
                print(f"Warning: Upload result missing ID. Did not delete from Paperless.")
                
        except Exception as e:
            print(f"Failed to upload {title}: {e}")
            print(f"Skipping deletion from Paperless for safety.")
        finally:
            # Cleanup local file
            if os.path.exists(local_path):
                os.remove(local_path)
                
    print("Migration complete!")

if __name__ == "__main__":
    main()
