#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/manage_calendar.py
Version:        2.1
Author:         Gemini CLI
Last Modified:  2026-02-20
Context:        http://trac.home.arpa/ticket/3080

Purpose:
    Wrapper for scripts/google_workspace_manager.py to maintain backward compatibility.
    Original purpose: Manage Google Calendar events and Tasks via CLI.

Usage:
    python3 manage_calendar.py setup
    python3 manage_calendar.py list [--max 10]
    python3 manage_calendar.py create_event "Summary" "2026-01-27T10:00:00" --duration 60
    python3 manage_calendar.py create_task "Title" --notes "Details"

Revision History:
    v2.1 (2026-02-20): Improved manager path resolution using os.path.dirname.
    v1.0: Original standalone script.
    v2.0 (2026-02-16): Refactored as a wrapper for unified manager.
================================================================================
"""
import sys
import subprocess
import argparse
import os

def run_command(cmd_args):
    # Determine the directory where this script resides
    script_dir = os.path.dirname(os.path.abspath(__file__))
    manager_path = os.path.join(script_dir, "google_workspace_manager.py")
    
    full_cmd = ["python3", manager_path] + cmd_args
    subprocess.run(full_cmd)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Manage Google Calendar and Tasks (Legacy Wrapper)')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Setup
    parser_setup = subparsers.add_parser('setup', help='Perform initial authentication')
    parser_setup.add_argument('--port', type=int, default=8080, help='Port for local server auth')

    # List Events
    parser_list = subparsers.add_parser('list', help='List upcoming events')
    parser_list.add_argument('--max', type=int, default=10, help='Max results')

    # Create Event
    parser_create = subparsers.add_parser('create_event', help='Create a new event')
    parser_create.add_argument('summary', help='Event title')
    parser_create.add_argument('start', help='Start time (ISO format)')
    parser_create.add_argument('--duration', type=int, default=60, help='Duration in minutes')
    parser_create.add_argument('--desc', help='Description')

    # Create Task
    parser_task = subparsers.add_parser('create_task', help='Create a new task')
    parser_task.add_argument('title', help='Task title')
    parser_task.add_argument('--notes', help='Task notes')
    
    args = parser.parse_args()

    if args.command == 'setup':
        run_command(['auth', '--port', str(args.port)])
    elif args.command == 'list':
        run_command(['cal-list', '--max', str(args.max)])
    elif args.command == 'create_event':
        cmd = ['cal-create', args.summary, args.start, '--duration', str(args.duration)]
        if args.desc:
            cmd += ['--desc', args.desc]
        run_command(cmd)
    elif args.command == 'create_task':
        cmd = ['tasks-create', args.title]
        if args.notes:
            cmd += ['--notes', args.notes]
        run_command(cmd)
