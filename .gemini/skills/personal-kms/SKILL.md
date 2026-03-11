---
name: personal-kms
description: Personal Knowledge Management (PKM) dispatcher. Use when the user needs to interact with Trac, WWOS MediaWiki, Google Workspace, or Nextcloud to create, link, or manage tickets, pages, tasks, calendar events, or contacts.
---

# Personal Knowledge Management (KMS)

This skill provides an umbrella for all knowledge management and administrative tasks across your heterogeneous toolset.

## Dispatcher Guide

Use these instructions directly to manage cross-linking and tool interactions:

### 1. Trac & WWOS Cross-linking
Mandatory bookmarklet-style formatting rules for linking Trac tickets to WWOS MediaWiki pages:

#### To WWOS (Prepended to content)
When adding a Trac ticket link to a WWOS page, **prepend** it to the very top of the page content in this format:
`'''[http://trac.gafla.us.com/ticket/<ID> trac #<ID> "<SUMMARY>"]'''`
- `<ID>`: The numeric Trac ticket ID.
- `<SUMMARY>`: The exact summary string of the Trac ticket.

#### To Trac (Added as comment)
When adding a WWOS page link to a Trac ticket, add it as a **new comment** in this format:
`'''[http://192.168.0.99/mediawiki/index.php/<PAGE_NAME> "WWOS PAGE: <PAGE_NAME>"]'''`
- `<PAGE_NAME>`: The exact title/name of the MediaWiki page.

### 2. Google Workspace (Gmail, Drive, Tasks, Calendar, Contacts)
Manage Google Workspace services using the `google_workspace_manager.py` tool.

- **Gmail**: Search with `python3 scripts/google_workspace_manager.py gmail-list --query "..."`. Use `--cite` for WWOS-style citations.
- **Drive**: Search with `python3 scripts/google_workspace_manager.py drive-search --query "..."`. Use `--cite` for WWOS-style citations. Update with `python3 scripts/google_workspace_manager.py drive-update "file_id" --name "new_name"`.
- **Calendar**: List with `cal-list`, create with `cal-create "Summary" "YYYY-MM-DDTHH:MM:SS"`.
- **Tasks**: List with `tasks-list`, create with `tasks-create "Title"`, update with `tasks-update "task_id"`.
- **Contacts**: Create with `people-create "Given" "Family"`.

### 3. WWOS-Style Citations
Use `scripts/wwos_citation.py` for generating standard formatted citations:
`python3 scripts/wwos_citation.py "URL" --title "TITLE" --source "SOURCE"`
Result: `[URL TITLE] <ref>SOURCE: [URL TITLE] retrieved YYYY-MM-DD</ref>`

### 4. Nextcloud Contact Management
Manage contacts via the Nextcloud MCP server.

- **Search**: `nextcloud_search_contacts(query="name or email")`.
- **Create**: `nextcloud_create_contact(fn="Full Name", email="user@example.com", tel="555-0199", ...)`.
- **Update**: `nextcloud_update_contact(uid="UUID", fn="New Name", email="new@example.com", ...)`. Note: This tool **appends** new values for multi-value fields by default.

## General Principles

1.  **Cross-pollination**: Whenever possible, cross-link between tools (e.g., link a Trac ticket in a Google Task or a WWOS page in a Nextcloud contact note).
2.  **Formatting Consistency**: Adhere strictly to the formatting rules defined above to maintain compatibility with the user's manual bookmarklets.
3.  **Proactive Documentation**: If a task is significant, ensure a corresponding record exists in the relevant system (usually Trac for tasks/bugs and WWOS for evergreen documentation).
