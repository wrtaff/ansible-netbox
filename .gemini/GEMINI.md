# Project Context: Ansible Control Repo

## Live Inventory
Here is the current active inventory file. Use this to look up IP addresses, groups, and variables when I ask about specific hosts.

@../inventory.ini
@../ansible.cfg

## Network Topology
(Optional: Add a brief description of your subnets or VLANs here)

# Available Tools

## Google Workspace Manager (`scripts/google_workspace_manager.py`)
This script provides unified access to Gmail, Google Drive, Calendar, and Tasks. It is designed for use by AI agents and automation scripts.

**Authentication:**
- Run `python3 scripts/google_workspace_manager.py auth --console` on the controller (or target) to generate/refresh credentials (`token.pickle`). Use `--console` for headless environments.

**Common Commands:**
- **Gmail:**
  - List: `python3 scripts/google_workspace_manager.py gmail-list --query "is:unread" --max 5`
  - Get: `python3 scripts/google_workspace_manager.py gmail-get <message_id>`
  - Send: `python3 scripts/google_workspace_manager.py gmail-send <to_email> <subject> <body>`
  - Draft: `python3 scripts/google_workspace_manager.py gmail-create-draft <to_email> <subject> <body>`
- **Drive:**
  - Search: `python3 scripts/google_workspace_manager.py drive-search --query "name contains 'Project Proposal'"`
  - Get Metadata: `python3 scripts/google_workspace_manager.py drive-get <file_id>`
  - Upload: `python3 scripts/google_workspace_manager.py drive-upload <file_path> --mime <mime_type>`
- **Calendar:**
  - List: `python3 scripts/google_workspace_manager.py cal-list --max 5`
  - Create: `python3 scripts/google_workspace_manager.py cal-create "Meeting" "2026-02-20T14:00:00" --duration 30`
  - Delete: `python3 scripts/google_workspace_manager.py cal-delete <event_id>`
- **Tasks:**
  - List: `python3 scripts/google_workspace_manager.py tasks-list`
  - Create: `python3 scripts/google_workspace_manager.py tasks-create "Buy milk" --notes "Almond milk"`

**Legacy Wrapper:**
`scripts/manage_calendar.py` exists as a backward-compatible wrapper for Calendar/Tasks operations, redirecting calls to the unified manager.
