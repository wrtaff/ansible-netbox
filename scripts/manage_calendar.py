#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/manage_calendar.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-01-27
Context:        http://trac.home.arpa/ticket/2978

Purpose:
    Manage Google Calendar events and Tasks via CLI.
    Supports creating events and tasks using OAuth 2.0.

Usage:
    python3 manage_calendar.py setup
    python3 manage_calendar.py list [--max 10]
    python3 manage_calendar.py create_event "Summary" "2026-01-27T10:00:00" --duration 60
    python3 manage_calendar.py create_task "Title" --notes "Details"
"""
import datetime
import os.path
import sys
import argparse
import pickle
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.pickle.
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/tasks'
]

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, 'credentials.json')
TOKEN_FILE = os.path.join(SCRIPT_DIR, 'token.pickle')

def get_creds():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                print(f"Error: {CREDENTIALS_FILE} not found. Please place your OAuth 2.0 Client credentials in this file.")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_console()
        with open(TOKEN_FILE, 'wb') as token:
            pickle.dump(creds, token)
    return creds

def create_event(summary, start_time_str, duration_mins=60, description=None):
    """Creates a calendar event."""
    creds = get_creds()
    service = build('calendar', 'v3', credentials=creds)

    # Parse time (assuming ISO format or simple YYYY-MM-DD HH:MM)
    try:
        start_time = datetime.datetime.fromisoformat(start_time_str)
    except ValueError:
        print("Error: Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
        return

    end_time = start_time + datetime.timedelta(minutes=duration_mins)

    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_time.isoformat(),
            'timeZone': 'UTC', # Adjust as needed or make configurable
        },
        'end': {
            'dateTime': end_time.isoformat(),
            'timeZone': 'UTC',
        },
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    print(f"Event created: {event.get('htmlLink')}")

def list_events(max_results=10):
    """Lists upcoming events."""
    creds = get_creds()
    service = build('calendar', 'v3', credentials=creds)

    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    print(f'Getting the upcoming {max_results} events')
    events_result = service.events().list(calendarId='primary', timeMin=now,
                                          maxResults=max_results, singleEvents=True,
                                          orderBy='startTime').execute()
    events = events_result.get('items', [])

    if not events:
        print('No upcoming events found.')
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        print(start, event['summary'])

def create_task(title, notes=None, due_date_str=None):
    """Creates a Google Task."""
    creds = get_creds()
    service = build('tasks', 'v1', credentials=creds)
    
    task = {
        'title': title,
        'notes': notes
    }
    
    if due_date_str:
         # Tasks API expects RFC 3339 timestamp
         task['due'] = due_date_str

    result = service.tasks().insert(tasklist='@default', body=task).execute()
    print(f"Task created: {result.get('title')} (ID: {result.get('id')})")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manage Google Calendar and Tasks')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Setup
    parser_setup = subparsers.add_parser('setup', help='Perform initial authentication')

    # List Events
    parser_list = subparsers.add_parser('list', help='List upcoming events')
    parser_list.add_argument('--max', type=int, default=10, help='Max results')

    # Create Event
    parser_create = subparsers.add_parser('create_event', help='Create a new event')
    parser_create.add_argument('summary', help='Event title')
    parser_create.add_argument('start', help='Start time (YYYY-MM-DDTHH:MM:SS)')
    parser_create.add_argument('--duration', type=int, default=60, help='Duration in minutes')
    parser_create.add_argument('--desc', help='Description')

    # Create Task
    parser_task = subparsers.add_parser('create_task', help='Create a new task')
    parser_task.add_argument('title', help='Task title')
    parser_task.add_argument('--notes', help='Task notes')
    
    args = parser.parse_args()

    if args.command == 'setup':
        get_creds()
        print("Authentication successful.")
    elif args.command == 'list':
        list_events(args.max)
    elif args.command == 'create_event':
        create_event(args.summary, args.start, args.duration, args.desc)
    elif args.command == 'create_task':
        create_task(args.title, args.notes)
