#!/usr/bin/env python3
"""
================================================================================
Filename:       create_vikunja_task.py
Version:        1.2
Author:         Gemini CLI
Last Modified:  2026-01-30

Purpose:
    Creates a new task in a Vikunja instance. This script is designed to be 
    portable and can be used locally or on remote hosts with Gemini CLI. It 
    supports setting the task title, description, project ID, "favorite" 
    status, and labels.

    Update 1.2:
    - Robust label handling: resolving existing labels by ID (case-insensitive) 
      and creating new ones on the fly if they don't exist.

Usage:
    # Set the API token in your environment:
    export VIKUNJA_API_TOKEN='your_token_here'

    # Create a simple task in the default project (Inbox):
    ./create_vikunja_task.py --title "My New Task"

    # Create a task with labels (prefixed with *):
    ./create_vikunja_task.py --title "Buy milk *grocery *urgent"
    # Result: Title "Buy milk", Labels ["grocery", "urgent"]

    # Create a task in a specific project with a description:
    ./create_vikunja_task.py --title "Task Name" --description "Detailed notes here" --project-id 5

    # Create a task and do NOT mark it as a favorite:
    ./create_vikunja_task.py --title "Low Priority Task" --no-favorite

    # Override the default host and provide the token as an argument:
    ./create_vikunja_task.py --title "External Task" --host "https://vikunja.example.com" --token "tk_..."

Arguments:
    --title          (Required) The summary/title of the task. Words starting
                     with '*' are extracted as labels.
    --description    The detailed description of the task (Markdown supported).
    --project-id     The ID of the project to add the task to (Default: 1 - Inbox).
    --no-favorite    If set, the task will not be marked as a favorite/starred.
    --host           The Vikunja instance URL (Default: http://todo.home.arpa).
    --token          The Vikunja API token (Overrides VIKUNJA_API_TOKEN env var).

Version History:
    v1.2 (2026-01-30) - Enhanced label support:
        - Now fetches existing labels to resolve IDs (case-insensitive).
        - Automatically creates new labels if they don't exist.
        - Fixes issue where labels were not being attached correctly.
    v1.1 (2026-01-30) - Added label parsing:
        - Words in the title starting with '*' are now extracted as labels.
    v1.0 (2026-01-30) - Initial version:
        - Portable Python implementation using urllib.

Dependencies:
    - Standard Python 3 libraries (urllib, json, ssl, argparse).

Exit Codes:
    0 - Success (Task created successfully)
    1 - Failure (API error, connection error, or missing configuration)
================================================================================
"""

import argparse
import os
import json
import urllib.request
import urllib.error
import ssl
import sys

def get_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx

def get_all_labels(host, token):
    url = f"{host}/api/v1/labels"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, context=get_ssl_context()) as response:
            if response.status == 200:
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Warning: Could not fetch labels: {e}")
    return []

def create_label(host, token, title):
    url = f"{host}/api/v1/labels"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    payload = json.dumps({"title": title}).encode('utf-8')
    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="PUT")
        with urllib.request.urlopen(req, context=get_ssl_context()) as response:
            if response.status in (200, 201):
                return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Warning: Could not create label '{title}': {e}")
    return None

def create_task(title, description="", project_id=1, is_favorite=True, host="http://todo.home.arpa", token=None, labels=None):
    if not token:
        token = os.getenv("VIKUNJA_API_TOKEN")
    
    if not token:
        print("Error: VIKUNJA_API_TOKEN environment variable not set and --token not provided.")
        sys.exit(1)

    # Resolve Labels
    resolved_labels = []
    if labels:
        print("Resolving labels...", end=" ", flush=True)
        existing_labels = get_all_labels(host, token)
        # Create a mapping for case-insensitive lookup
        label_map = {l['title'].lower(): l for l in existing_labels}
        
        for label_name in labels:
            existing = label_map.get(label_name.lower())
            if existing:
                resolved_labels.append({"id": existing['id']})
            else:
                print(f"(Creating new label '{label_name}')...", end=" ", flush=True)
                new_label = create_label(host, token, label_name)
                if new_label:
                    resolved_labels.append({"id": new_label['id']})
        print("Done.")

    url = f"{host}/api/v1/projects/{project_id}/tasks"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "title": title,
        "description": description,
        "is_favorite": is_favorite
    }
    
    if resolved_labels:
        payload["labels"] = resolved_labels
    
    json_payload = json.dumps(payload).encode('utf-8')
    
    try:
        req = urllib.request.Request(url, data=json_payload, headers=headers, method="PUT")
        with urllib.request.urlopen(req, context=get_ssl_context()) as response:
            if response.status in (200, 201):
                result = json.loads(response.read().decode('utf-8'))
                print(f"Success: Task created with ID {result.get('id')}")
                print(f"Title: {result.get('title')}")
                if resolved_labels:
                    print(f"Labels Attached: {len(resolved_labels)}")
                print(f"Link: {host}/tasks/{result.get('id')}")
            else:
                print(f"Error: Unexpected status code {response.status}")
                print(response.read().decode('utf-8'))
                sys.exit(1)

    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(e.read().decode('utf-8'))
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"URL Error: {e.reason}")
        sys.exit(1)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Create a task in Vikunja.")
    parser.add_argument("--title", required=True, help="Task title")
    parser.add_argument("--description", default="", help="Task description (Markdown supported)")
    parser.add_argument("--project-id", type=int, default=1, help="Project ID (Default: 1 for Inbox)")
    parser.add_argument("--no-favorite", action="store_true", help="Do not mark as favorite (Default: Favorite)")
    parser.add_argument("--host", default="http://todo.home.arpa", help="Vikunja host URL")
    parser.add_argument("--token", help="API Token (overrides VIKUNJA_API_TOKEN env var)")
    
    args = parser.parse_args()
    
    # Parse labels from title
    words = args.title.split()
    labels = [w[1:] for w in words if w.startswith('*')]
    clean_title = ' '.join([w for w in words if not w.startswith('*')])
    
    create_task(
        title=clean_title,
        description=args.description,
        project_id=args.project_id,
        is_favorite=not args.no_favorite,
        host=args.host.rstrip('/'),
        token=args.token,
        labels=labels
    )

if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
