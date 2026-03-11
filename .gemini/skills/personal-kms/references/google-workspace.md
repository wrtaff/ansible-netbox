# Google Workspace Management

This reference provides instructions for managing Google Workspace services (Calendar, Tasks, Gmail, Drive, Contacts) using the `google_workspace_manager.py` script.

## Core Tool: `google_workspace_manager.py`

This unified tool provides both human-readable and JSON output for AI agent consumption.

### Usage Examples

1.  **Gmail Message Search/List**:
    - Query: `python3 scripts/google_workspace_manager.py gmail-list --query "your query"`
    - Use this to find specific emails to summarize or act upon.
2.  **Drive File Search/Update**:
    - Search: `python3 scripts/google_workspace_manager.py drive-search --query "name contains '...']"`
    - Update: `python3 scripts/google_workspace_manager.py drive-update "file_id" --name "new_name"`
3.  **Calendar Events**:
    - List: `python3 scripts/google_workspace_manager.py cal-list`
    - Create: `python3 scripts/google_workspace_manager.py cal-create "Summary" "YYYY-MM-DDTHH:MM:SS" --duration 60`
4.  **Tasks Creation/Update**:
    - List: `python3 scripts/google_workspace_manager.py tasks-list`
    - Create: `python3 scripts/google_workspace_manager.py tasks-create "Title" --notes "Notes"`
    - Update: `python3 scripts/google_workspace_manager.py tasks-update "task_id" --title "New Title"`
5.  **Contacts (People API)**:
    - Create: `python3 scripts/google_workspace_manager.py people-create "Given" "Family" --job "Title"`

## Authentication Workflow

If the tool reports a credential error, follow these steps:
1.  Run: `python3 scripts/google_workspace_manager.py auth --console`
2.  Provide the authorization URL to the user.
3.  Ask the user for the authorization code.
4.  Feed the code back into the command line to refresh `token.pickle`.

## Best Practices

- **JSON Output**: When parsing data for further automation, use the `--format json` flag if available in the script's `output` function to ensure deterministic parsing.
- **Proactive Sync**: When a Trac ticket involves a meeting or a deadline, proactively offer to create a Google Calendar event or a Task.
- **Drafting**: Use `gmail-create-draft` instead of `gmail-send` when the content is complex or requires user final approval.
