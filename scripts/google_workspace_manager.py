#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/google_workspace_manager.py
Version:        1.1
Author:         Gemini CLI
Last Modified:  2026-02-16
Context:        http://trac.home.arpa/ticket/3080

Purpose:
    Unified manager for Google Workspace services (Calendar, Tasks, Gmail, Drive).
    Provides both human-readable and JSON output for AI agent consumption.

Usage:
    python3 google_workspace_manager.py auth
    python3 google_workspace_manager.py gmail-list [--query "query"]
    python3 google_workspace_manager.py drive-search [--query "name contains '...']

Revision History:
    v1.0 (2026-02-16): Initial version with basic Gmail/Drive/Cal/Tasks.
    v1.1 (2026-02-16): Added attachment retrieval and file upload support.
================================================================================
"""
import datetime
import os.path
import sys
import argparse
import pickle
import json
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# Scopes required for the unified assistant
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/drive'
]

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(SCRIPT_DIR, 'token.pickle')

def get_creds(port=8080):
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    
    # Check if scopes in token match current SCOPES
    if creds and set(SCOPES).issubset(set(creds.scopes)):
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                creds = None
    else:
        # Scopes have changed or no creds, re-auth required
        creds = None

    if not creds or not creds.valid:
        if not os.path.exists(CREDENTIALS_FILE):
            print(f"Error: {CREDENTIALS_FILE} not found.")
            sys.exit(1)
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        # Note: run_local_server might not work in non-interactive environment
        # But for first run, user will provide input.
        creds = flow.run_local_server(host='127.0.0.1', port=port, prompt='consent', open_browser=False)
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    return creds

def output(data, format='text'):
    if format == 'json':
        print(json.dumps(data, indent=2))
    else:
        # Standardize textual output if needed
        if isinstance(data, dict):
            print(json.dumps(data, indent=2))
        elif isinstance(data, list):
            for item in data:
                print(item)
        else:
            print(data)

# --- GMAIL FUNCTIONS ---

def gmail_list_messages(query='', max_results=10, output_format='text'):
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)
    try:
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        
        full_messages = []
        for msg in messages:
            m = service.users().messages().get(userId='me', id=msg['id'], format='minimal').execute()
            full_messages.append({
                'id': m['id'],
                'snippet': m['snippet']
            })
        
        output(full_messages, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

def gmail_get_message(message_id, output_format='text'):
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)
    try:
        message = service.users().messages().get(userId='me', id=message_id).execute()
        # Basic parsing of message
        headers = message['payload'].get('headers', [])
        subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
        from_email = next((h['value'] for h in headers if h['name'].lower() == 'from'), 'Unknown')
        
        # Extract body
        body = ""
        if 'parts' in message['payload']:
            for part in message['payload']['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode()
                    break
        else:
            data = message['payload']['body'].get('data')
            if data:
                body = base64.urlsafe_b64decode(data).decode()

        result = {
            'id': message['id'],
            'subject': subject,
            'from': from_email,
            'snippet': message['snippet'],
            'body': body,
            'internalDate': message['internalDate'],
            'attachments': [
                {'id': p['body']['attachmentId'], 'filename': p['filename'], 'mimeType': p['mimeType']}
                for p in message['payload'].get('parts', []) if 'attachmentId' in p['body']
            ]
        }
        output(result, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

def gmail_download_attachment(message_id, attachment_id, filename, output_dir=None):
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)
    try:
        attachment = service.users().messages().attachments().get(
            userId='me', messageId=message_id, id=attachment_id).execute()
        data = attachment['data']
        file_data = base64.urlsafe_b64decode(data.encode('UTF-8'))
        
        if output_dir:
            path = os.path.join(output_dir, filename)
        else:
            path = filename

        with open(path, 'wb') as f:
            f.write(file_data)
        return path
    except HttpError as error:
        print(f"Error downloading attachment: {error}")
        return None

# --- DRIVE FUNCTIONS ---

def drive_upload_file(file_path, mimetype=None, output_format='text'):
    creds = get_creds()
    service = build('drive', 'v3', credentials=creds)
    try:
        file_metadata = {'name': os.path.basename(file_path)}
        media = MediaFileUpload(file_path, mimetype=mimetype, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id, name').execute()
        output(file, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)


def drive_search(query=None, max_results=10, output_format='text'):
    creds = get_creds()
    service = build('drive', 'v3', credentials=creds)
    try:
        results = service.files().list(
            q=query, pageSize=max_results, fields="nextPageToken, files(id, name, mimeType)").execute()
        items = results.get('files', [])
        output(items, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

def drive_get_file_metadata(file_id, output_format='text'):
    creds = get_creds()
    service = build('drive', 'v3', credentials=creds)
    try:
        file = service.files().get(fileId=file_id, fields='id, name, mimeType, description, webViewLink').execute()
        output(file, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

# --- CALENDAR FUNCTIONS ---

def calendar_list_events(max_results=10, output_format='text'):
    creds = get_creds()
    service = build('calendar', 'v3', credentials=creds)
    try:
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        results = service.events().list(calendarId='primary', timeMin=now,
                                        maxResults=max_results, singleEvents=True,
                                        orderBy='startTime').execute()
        events = results.get('items', [])
        output(events, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

def calendar_create_event(summary, start_time_str, duration_mins=60, description=None, output_format='text'):
    creds = get_creds()
    service = build('calendar', 'v3', credentials=creds)
    try:
        start_time = datetime.datetime.fromisoformat(start_time_str)
        end_time = start_time + datetime.timedelta(minutes=duration_mins)
        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time.isoformat(), 'timeZone': 'UTC'},
            'end': {'dateTime': end_time.isoformat(), 'timeZone': 'UTC'},
        }
        event = service.events().insert(calendarId='primary', body=event).execute()
        output(event, output_format)
    except Exception as error:
        output({'error': str(error)}, output_format)

# --- TASKS FUNCTIONS ---

def tasks_list_tasks(max_results=10, output_format='text'):
    creds = get_creds()
    service = build('tasks', 'v1', credentials=creds)
    try:
        results = service.tasks().list(tasklist='@default', maxResults=max_results).execute()
        tasks = results.get('items', [])
        output(tasks, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

def tasks_create_task(title, notes=None, due_date_str=None, output_format='text'):
    creds = get_creds()
    service = build('tasks', 'v1', credentials=creds)
    try:
        task = {'title': title, 'notes': notes}
        if due_date_str:
            task['due'] = due_date_str
        result = service.tasks().insert(tasklist='@default', body=task).execute()
        output(result, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

# --- MAIN CLI ---

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Google Workspace Unified Manager')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='Output format')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Auth
    parser_auth = subparsers.add_parser('auth', help='Refresh or establish authentication')
    parser_auth.add_argument('--port', type=int, default=8080, help='Port for local server auth (default: 8080)')

    # Gmail List
    parser_gmail_list = subparsers.add_parser('gmail-list', help='List Gmail messages')
    parser_gmail_list.add_argument('--query', default='', help='Gmail search query')
    parser_gmail_list.add_argument('--max', type=int, default=10, help='Max results')

    # Gmail Get
    parser_gmail_get = subparsers.add_parser('gmail-get', help='Get message details')
    parser_gmail_get.add_argument('id', help='Message ID')

    # Drive Search
    parser_drive_search = subparsers.add_parser('drive-search', help='Search Google Drive')
    parser_drive_search.add_argument('--query', help='Drive query (e.g. "name contains \'resume\'")')
    parser_drive_search.add_argument('--max', type=int, default=10, help='Max results')

    # Drive Get
    parser_drive_get = subparsers.add_parser('drive-get', help='Get file metadata')
    parser_drive_get.add_argument('id', help='File ID')

    # Drive Upload
    parser_drive_upload = subparsers.add_parser('drive-upload', help='Upload a file to Drive')
    parser_drive_upload.add_argument('file_path', help='Path to local file')
    parser_drive_upload.add_argument('--mime', help='MIME type')

    # Calendar List
    parser_cal_list = subparsers.add_parser('cal-list', help='List calendar events')
    parser_cal_list.add_argument('--max', type=int, default=10, help='Max results')

    # Calendar Create
    parser_cal_create = subparsers.add_parser('cal-create', help='Create calendar event')
    parser_cal_create.add_argument('summary', help='Event summary')
    parser_cal_create.add_argument('start', help='Start time (ISO format)')
    parser_cal_create.add_argument('--duration', type=int, default=60, help='Duration in minutes')
    parser_cal_create.add_argument('--desc', help='Description')

    # Tasks List
    parser_tasks_list = subparsers.add_parser('tasks-list', help='List tasks')
    parser_tasks_list.add_argument('--max', type=int, default=10, help='Max results')

    # Tasks Create
    parser_tasks_create = subparsers.add_parser('tasks-create', help='Create task')
    parser_tasks_create.add_argument('title', help='Task title')
    parser_tasks_create.add_argument('--notes', help='Notes')
    parser_tasks_create.add_argument('--due', help='Due date (ISO format)')

    args = parser.parse_args()

    if args.command == 'auth':
        get_creds(port=args.port)
        print("Authentication verified.")
    elif args.command == 'gmail-list':
        gmail_list_messages(args.query, args.max, args.format)
    elif args.command == 'gmail-get':
        gmail_get_message(args.id, args.format)
    elif args.command == 'drive-search':
        drive_search(args.query, args.max, args.format)
    elif args.command == 'drive-get':
        drive_get_file_metadata(args.id, args.format)
    elif args.command == 'drive-upload':
        drive_upload_file(args.file_path, args.mime, args.format)
    elif args.command == 'cal-list':
        calendar_list_events(args.max, args.format)
    elif args.command == 'cal-create':
        calendar_create_event(args.summary, args.start, args.duration, args.desc, args.format)
    elif args.command == 'tasks-list':
        tasks_list_tasks(args.max, args.format)
    elif args.command == 'tasks-create':
        tasks_create_task(args.title, args.notes, args.due, args.format)
