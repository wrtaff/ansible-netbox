#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/google_workspace_manager.py
Version:        1.12
Author:         Gemini CLI
Last Modified:  2026-02-27
Context:        http://trac.home.arpa/ticket/3080

Purpose:
    Unified manager for Google Workspace services (Calendar, Tasks, Gmail, Drive, Contacts).
    Provides both human-readable and JSON output for AI agent consumption.

Usage:
    python3 google_workspace_manager.py auth [--console]
    python3 google_workspace_manager.py gmail-list [--query "query"]
    python3 google_workspace_manager.py drive-search [--query "name contains '...']
    python3 google_workspace_manager.py people-create "Given" "Family" --job "Title"

Revision History:
    v1.0 (2026-02-16): Initial version with basic Gmail/Drive/Cal/Tasks.
    v1.1 (2026-02-16): Added attachment retrieval and file upload support.
    v1.2 (2026-02-17): Added gmail-send functionality.
    v1.3 (2026-02-17): Added calendar-delete functionality.
    v1.4 (2026-02-17): Added gmail-get-by-header functionality.
    v1.5 (2026-02-18): Added gmail-create-draft functionality.
    v1.6 (2026-02-19): Added cal-get, attendees to cal-create, and fixed newline handling in Gmail.
    v1.7 (2026-02-20): Added console authentication support for headless environments.
    v1.8 (2026-02-21): Added drive-export functionality for exporting Google Docs to text.
    v1.9 (2026-02-25): Added attachment support to gmail-send and gmail-create-draft.
    v1.10 (2026-02-25): Added drive-download support for binary files.
    v1.11 (2026-02-26): Replaced deprecated run_console with manual code entry flow and consolidated remote features.
    v1.12 (2026-02-27): Added People API support for creating contacts.
================================================================================
"""
import datetime
import os.path
import sys
import argparse
import pickle
import json
import base64
import re
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
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/contacts'
]

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(SCRIPT_DIR, 'token.pickle')

def get_creds(port=8080, use_console=False):
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
        
        if use_console:
            flow = InstalledAppFlow.from_client_secrets_file(
                CREDENTIALS_FILE, SCOPES, redirect_uri='urn:ietf:wg:oauth:2.0:oob')
            auth_url, _ = flow.authorization_url(prompt='consent')
            print(f'Please visit this URL to authorize this application: {auth_url}')
            code = input('Enter the authorization code: ')
            flow.fetch_token(code=code)
            creds = flow.credentials
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            # Note: run_local_server might not work in non-interactive environment
            # But for first run, user will provide input.
            creds = flow.run_local_server(host='127.0.0.1', port=port, prompt='consent', open_browser=True)
            
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

def gmail_send_message(to, subject, body, attachment_path=None, output_format='text'):
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)
    try:
        from email.message import EmailMessage
        import mimetypes
        message = EmailMessage()
        # Handle literal \n as newlines
        body = body.replace('\\n', '\n')
        message.set_content(body)
        message['To'] = to
        message['Subject'] = subject
        
        if attachment_path and os.path.exists(attachment_path):
            mime_type, _ = mimetypes.guess_type(attachment_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            main_type, sub_type = mime_type.split('/', 1)
            
            with open(attachment_path, 'rb') as fp:
                attachment_data = fp.read()
            message.add_attachment(attachment_data, maintype=main_type, subtype=sub_type, filename=os.path.basename(attachment_path))

        # encoded message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {
            'raw': encoded_message
        }
        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        output(send_message, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

def gmail_create_draft(to, subject, body, attachment_path=None, output_format='text'):
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)
    try:
        from email.message import EmailMessage
        import mimetypes
        message = EmailMessage()
        # Handle literal \n as newlines
        body = body.replace('\\n', '\n')
        message.set_content(body)
        message['To'] = to
        message['Subject'] = subject

        if attachment_path and os.path.exists(attachment_path):
            mime_type, _ = mimetypes.guess_type(attachment_path)
            if mime_type is None:
                mime_type = 'application/octet-stream'
            main_type, sub_type = mime_type.split('/', 1)
            
            with open(attachment_path, 'rb') as fp:
                attachment_data = fp.read()
            message.add_attachment(attachment_data, maintype=main_type, subtype=sub_type, filename=os.path.basename(attachment_path))
        
        # encoded message
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_draft = {
            'message': {
                'raw': encoded_message
            }
        }
        draft = service.users().drafts().create(userId="me", body=create_draft).execute()
        output(draft, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

def gmail_get_by_header(header_string, output_format='text'):
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)
    try:
        # Extract Message-ID, handling potential artifacts like spaces before @
        match = re.search(r'Message-ID:\s*<([^>]+)>', header_string, re.IGNORECASE)
        if not match:
            output({'error': 'Message-ID not found in header string'}, output_format)
            return

        msg_id_header = match.group(1).strip()
        query = f'rfc822msgid:{msg_id_header}'
        
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        
        if not messages:
            # Try stripping spaces if it failed
            clean_msg_id = msg_id_header.replace(' ', '')
            if clean_msg_id != msg_id_header:
                query = f'rfc822msgid:{clean_msg_id}'
                results = service.users().messages().list(userId='me', q=query).execute()
                messages = results.get('messages', [])

        if not messages:
            output({'error': f'No message found for Message-ID: {msg_id_header}'}, output_format)
            return
            
        gmail_id = messages[0]['id']
        gmail_get_message(gmail_id, output_format)
    except Exception as error:
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

def drive_download_file(file_id, output_path, output_format='text'):
    creds = get_creds()
    service = build('drive', 'v3', credentials=creds)
    try:
        from googleapiclient.http import MediaIoBaseDownload
        import io
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        
        with open(output_path, 'wb') as f:
            f.write(fh.getvalue())
        output({'result': f'Downloaded to {output_path}'}, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

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

def drive_export_file(file_id, mime_type='text/plain', output_file=None):
    creds = get_creds()
    service = build('drive', 'v3', credentials=creds)
    try:
        request = service.files().export_media(fileId=file_id, mimeType=mime_type)
        file_data = request.execute()
        
        if output_file:
            with open(output_file, 'wb') as f:
                f.write(file_data)
            print(f"Exported to {output_file}")
        else:
            # Try to decode as text for stdout
            try:
                print(file_data.decode('utf-8'))
            except:
                print(file_data)
    except HttpError as error:
        print(f"Error exporting file: {error}")

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

def calendar_create_event(summary, start_time_str, duration_mins=60, description=None, attendees=None, output_format='text'):
    creds = get_creds()
    service = build('calendar', 'v3', credentials=creds)
    try:
        start_time = datetime.datetime.fromisoformat(start_time_str)
        end_time = start_time + datetime.timedelta(minutes=duration_mins)
        event = {
            'summary': summary,
            'description': description,
            'start': {'dateTime': start_time.isoformat()},
            'end': {'dateTime': end_time.isoformat()},
        }
        if attendees:
            event['attendees'] = [{'email': email.strip()} for email in attendees.split(',')]
        
        event = service.events().insert(calendarId='primary', body=event).execute()
        output(event, output_format)
    except Exception as error:
        output({'error': str(error)}, output_format)

def calendar_get_event(event_id, output_format='text'):
    creds = get_creds()
    service = build('calendar', 'v3', credentials=creds)
    try:
        event = service.events().get(calendarId='primary', eventId=event_id).execute()
        output(event, output_format)
    except HttpError as error:
        output({'error': str(error)}, output_format)

def calendar_delete_event(event_id, output_format='text'):
    creds = get_creds()
    service = build('calendar', 'v3', credentials=creds)
    try:
        service.events().delete(calendarId='primary', eventId=event_id).execute()
        output({'result': f'Event {event_id} deleted'}, output_format)
    except HttpError as error:
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

# --- CONTACTS FUNCTIONS ---

def contacts_create_contact(given_name, family_name, job_title=None, company=None, phone=None, email=None, notes=None, output_format='text'):
    creds = get_creds()
    service = build('people', 'v1', credentials=creds)
    try:
        contact_body = {
            "names": [{"givenName": given_name, "familyName": family_name}],
        }
        if job_title or company:
            contact_body["organizations"] = [{
                "name": company if company else "",
                "title": job_title if job_title else "",
                "type": "work"
            }]
        if phone:
            contact_body["phoneNumbers"] = [{"value": phone, "type": "mobile"}]
        if email:
            contact_body["emailAddresses"] = [{"value": email, "type": "work"}]
        if notes:
            contact_body["biographies"] = [{"value": notes}]
            
        result = service.people().createContact(body=contact_body).execute()
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
    parser_auth.add_argument('--console', action='store_true', help='Use console-based auth flow (for headless servers)')

    # People Create
    parser_people_create = subparsers.add_parser('people-create', help='Create a Google Contact')
    parser_people_create.add_argument('given_name', help='Given name')
    parser_people_create.add_argument('family_name', help='Family name')
    parser_people_create.add_argument('--job', help='Job title')
    parser_people_create.add_argument('--company', help='Company name')
    parser_people_create.add_argument('--phone', help='Phone number')
    parser_people_create.add_argument('--email', help='Email address')
    parser_people_create.add_argument('--notes', help='Notes or biography')

    # Gmail List
    parser_gmail_list = subparsers.add_parser('gmail-list', help='List Gmail messages')
    parser_gmail_list.add_argument('--query', default='', help='Gmail search query')
    parser_gmail_list.add_argument('--max', type=int, default=10, help='Max results')

    # Gmail Send
    parser_gmail_send = subparsers.add_parser('gmail-send', help='Send a Gmail message')
    parser_gmail_send.add_argument('to', help='Recipient email address')
    parser_gmail_send.add_argument('subject', help='Email subject')
    parser_gmail_send.add_argument('body', help='Email body')
    parser_gmail_send.add_argument('--attachment', help='Path to file to attach')

    # Gmail Create Draft
    parser_gmail_draft = subparsers.add_parser('gmail-create-draft', help='Create a Gmail draft')
    parser_gmail_draft.add_argument('to', help='Recipient email address')
    parser_gmail_draft.add_argument('subject', help='Email subject')
    parser_gmail_draft.add_argument('body', help='Email body')
    parser_gmail_draft.add_argument('--attachment', help='Path to file to attach')

    # Gmail Get
    parser_gmail_get = subparsers.add_parser('gmail-get', help='Get message details')
    parser_gmail_get.add_argument('id', help='Message ID')

    # Gmail Get by Header
    parser_gmail_header = subparsers.add_parser('gmail-get-by-header', help='Get message details by header string')
    parser_gmail_header.add_argument('header', help='Full email header string')

    # Drive Search
    parser_drive_search = subparsers.add_parser('drive-search', help='Search Google Drive')
    parser_drive_search.add_argument('--query', help='Drive query (e.g. "name contains \'resume\'")')
    parser_drive_search.add_argument('--max', type=int, default=10, help='Max results')

    # Drive Get
    parser_drive_get = subparsers.add_parser('drive-get', help='Get file metadata')
    parser_drive_get.add_argument('id', help='File ID')

    # Drive Download
    parser_drive_download = subparsers.add_parser('drive-download', help='Download a file from Drive')
    parser_drive_download.add_argument('id', help='File ID')
    parser_drive_download.add_argument('out', help='Output file path')

    # Drive Upload
    parser_drive_upload = subparsers.add_parser('drive-upload', help='Upload a file to Drive')
    parser_drive_upload.add_argument('file_path', help='Path to local file')
    parser_drive_upload.add_argument('--mime', help='MIME type')

    # Drive Export
    parser_drive_export = subparsers.add_parser('drive-export', help='Export a Google Doc')
    parser_drive_export.add_argument('id', help='File ID')
    parser_drive_export.add_argument('--mime', default='text/plain', help='MIME type to export to (default: text/plain)')
    parser_drive_export.add_argument('--out', help='Output file path')

    # Calendar List
    parser_cal_list = subparsers.add_parser('cal-list', help='List calendar events')
    parser_cal_list.add_argument('--max', type=int, default=10, help='Max results')

    # Calendar Create
    parser_cal_create = subparsers.add_parser('cal-create', help='Create calendar event')
    parser_cal_create.add_argument('summary', help='Event summary')
    parser_cal_create.add_argument('start', help='Start time (ISO format)')
    parser_cal_create.add_argument('--duration', type=int, default=60, help='Duration in minutes')
    parser_cal_create.add_argument('--desc', help='Description')
    parser_cal_create.add_argument('--attendees', help='Comma-separated attendee emails')

    # Calendar Delete
    parser_cal_delete = subparsers.add_parser('cal-delete', help='Delete calendar event')
    parser_cal_delete.add_argument('id', help='Event ID')

    # Calendar Get
    parser_cal_get = subparsers.add_parser('cal-get', help='Get calendar event details')
    parser_cal_get.add_argument('id', help='Event ID')

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
        get_creds(port=args.port, use_console=args.console)
        print("Authentication verified.")
    elif args.command == 'people-create':
        contacts_create_contact(args.given_name, args.family_name, args.job, args.company, args.phone, args.email, args.notes, args.format)
    elif args.command == 'gmail-list':
        gmail_list_messages(args.query, args.max, args.format)
    elif args.command == 'gmail-send':
        gmail_send_message(args.to, args.subject, args.body, args.attachment, args.format)
    elif args.command == 'gmail-create-draft':
        gmail_create_draft(args.to, args.subject, args.body, args.attachment, args.format)
    elif args.command == 'gmail-get':
        gmail_get_message(args.id, args.format)
    elif args.command == 'gmail-get-by-header':
        gmail_get_by_header(args.header, args.format)
    elif args.command == 'drive-search':
        drive_search(args.query, args.max, args.format)
    elif args.command == 'drive-get':
        drive_get_file_metadata(args.id, args.format)
    elif args.command == 'drive-download':
        drive_download_file(args.id, args.out, args.format)
    elif args.command == 'drive-export':
        drive_export_file(args.id, args.mime, args.out)
    elif args.command == 'drive-upload':
        drive_upload_file(args.file_path, args.mime, args.format)
    elif args.command == 'cal-list':
        calendar_list_events(args.max, args.format)
    elif args.command == 'cal-create':
        calendar_create_event(args.summary, args.start, args.duration, args.desc, args.attendees, args.format)
    elif args.command == 'cal-get':
        calendar_get_event(args.id, args.format)
    elif args.command == 'cal-delete':
        calendar_delete_event(args.id, args.format)
    elif args.command == 'tasks-list':
        tasks_list_tasks(args.max, args.format)
    elif args.command == 'tasks-create':
        tasks_create_task(args.title, args.notes, args.due, args.format)
