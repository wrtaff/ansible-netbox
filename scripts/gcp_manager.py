#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/gcp_manager.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-03-11
Context:        http://trac.gafla.us.com/ticket/3169

Purpose:
    Manager for Google Cloud Platform (GCP) resources via API.
    Handles projects, billing, budget alerts, and App Engine status.

Usage:
    python3 gcp_manager.py list-projects
    python3 gcp_manager.py list-billing
    python3 gcp_manager.py get-gae-status <project_id>
    python3 gcp_manager.py disable-gae <project_id>

Revision History:
    v1.0 (2026-03-11): Initial version with project, billing, and GAE tools.

Notes:
    Uses credentials from scripts/token.pickle.
================================================================================
"""

import os
import sys
import json
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(SCRIPT_DIR, 'token.pickle')

# Additional scopes needed for GCP management
GCP_SCOPES = [
    'https://www.googleapis.com/auth/cloud-platform',
    'https://www.googleapis.com/auth/cloud-billing'
]

def get_creds():
    if not os.path.exists(TOKEN_FILE):
        print(f"Error: {TOKEN_FILE} not found. Please run google_workspace_manager.py auth first.")
        sys.exit(1)
    
    with open(TOKEN_FILE, 'rb') as token:
        creds = pickle.load(token)
    
    # Check if creds has cloud-platform scope
    if not any(scope in creds.scopes for scope in GCP_SCOPES):
        print("Error: Current token.pickle does not have cloud-platform scopes.")
        print("Please re-authenticate with broader scopes.")
        sys.exit(1)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    return creds

def list_projects():
    creds = get_creds()
    service = build('cloudresourcemanager', 'v1', credentials=creds)
    try:
        request = service.projects().list()
        response = request.execute()
        projects = response.get('projects', [])
        print(json.dumps(projects, indent=2))
    except HttpError as e:
        print(f"HTTP Error: {e}")

def list_billing_accounts():
    creds = get_creds()
    service = build('cloudbilling', 'v1', credentials=creds)
    try:
        request = service.billingAccounts().list()
        response = request.execute()
        accounts = response.get('billingAccounts', [])
        print(json.dumps(accounts, indent=2))
    except HttpError as e:
        print(f"HTTP Error: {e}")

def get_gae_status(project_id):
    creds = get_creds()
    service = build('appengine', 'v1', credentials=creds)
    try:
        # Apps.get returns the application resource
        app = service.apps().get(appsId=project_id).execute()
        print(json.dumps(app, indent=2))
    except HttpError as e:
        if e.resp.status == 404:
            print(f"No App Engine application found for project {project_id}.")
        else:
            print(f"HTTP Error: {e}")

def disable_gae(project_id):
    creds = get_creds()
    service = build('appengine', 'v1', credentials=creds)
    try:
        # Patch the servingStatus to USER_DISABLED
        body = {'servingStatus': 'USER_DISABLED'}
        operation = service.apps().patch(appsId=project_id, updateMask='servingStatus', body=body).execute()
        print(f"Disable operation initiated: {operation.get('name')}")
    except HttpError as e:
        print(f"HTTP Error: {e}")

def create_project(project_id, name):
    creds = get_creds()
    service = build('cloudresourcemanager', 'v1', credentials=creds)
    try:
        body = {
            'projectId': project_id,
            'name': name
        }
        operation = service.projects().create(body=body).execute()
        print(f"Project creation initiated: {operation.get('name')}")
    except HttpError as e:
        print(f"HTTP Error: {e}")

def link_billing_account(project_id, billing_account_name):
    creds = get_creds()
    service = build('cloudbilling', 'v1', credentials=creds)
    try:
        body = {
            'billingAccountName': billing_account_name,
            'billingEnabled': True
        }
        billing_info = service.projects().updateBillingInfo(name=f"projects/{project_id}", body=body).execute()
        print(f"Billing linked: {json.dumps(billing_info, indent=2)}")
    except HttpError as e:
        print(f"HTTP Error: {e}")

def create_pubsub_topic(project_id, topic_name):
    creds = get_creds()
    service = build('pubsub', 'v1', credentials=creds)
    try:
        topic_path = f"projects/{project_id}/topics/{topic_name}"
        topic = service.projects().topics().create(name=topic_path, body={}).execute()
        print(f"Topic created: {json.dumps(topic, indent=2)}")
    except HttpError as e:
        print(f"HTTP Error: {e}")

def create_budget_alert(billing_account_id, project_id, topic_name):
    creds = get_creds()
    service = build('billingbudgets', 'v1', credentials=creds)
    try:
        # parent is billingAccounts/{billingAccountId}
        parent = billing_account_id
        budget = {
            'displayName': f"GAE Budget Alert - {project_id}",
            'budgetFilter': {
                'projects': [f"projects/{project_id}"]
            },
            'amount': {
                'specifiedAmount': {
                    'currencyCode': 'USD',
                    'units': '0',
                    'nanos': 10000000 # $0.01
                }
            },
            'thresholdRules': [
                {'thresholdPercent': 1.0, 'spendBasis': 'CURRENT_SPEND'},
                {'thresholdPercent': 0.5, 'spendBasis': 'CURRENT_SPEND'}
            ],
            'notificationsRule': {
                'pubsubTopic': f"projects/{project_id}/topics/{topic_name}",
                'schemaVersion': '1.0'
            }
        }
        response = service.billingAccounts().budgets().create(parent=parent, body=budget).execute()
        print(f"Budget created: {json.dumps(response, indent=2)}")
    except HttpError as e:
        print(f"HTTP Error: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: gcp_manager.py <command> [args]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list-projects":
        list_projects()
    elif cmd == "list-billing":
        list_billing_accounts()
    elif cmd == "create-project":
        if len(sys.argv) < 4:
            print("Usage: gcp_manager.py create-project <project_id> <name>")
            sys.exit(1)
        create_project(sys.argv[2], sys.argv[3])
    elif cmd == "link-billing":
        if len(sys.argv) < 4:
            print("Usage: gcp_manager.py link-billing <project_id> <billing_account_name>")
            sys.exit(1)
        link_billing_account(sys.argv[2], sys.argv[3])
    elif cmd == "create-topic":
        if len(sys.argv) < 4:
            print("Usage: gcp_manager.py create-topic <project_id> <topic_name>")
            sys.exit(1)
        create_pubsub_topic(sys.argv[2], sys.argv[3])
    elif cmd == "create-budget":
        if len(sys.argv) < 5:
            print("Usage: gcp_manager.py create-budget <billing_account_id> <project_id> <topic_name>")
            sys.exit(1)
        create_budget_alert(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "get-gae-status":
        if len(sys.argv) < 3:
            print("Usage: gcp_manager.py get-gae-status <project_id>")
            sys.exit(1)
        get_gae_status(sys.argv[2])
    elif cmd == "disable-gae":
        if len(sys.argv) < 3:
            print("Usage: gcp_manager.py disable-gae <project_id>")
            sys.exit(1)
        disable_gae(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()
