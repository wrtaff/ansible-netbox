# Nextcloud Contact Management

This reference provides instructions for managing contacts via the Nextcloud MCP server.

## Core Tool: Nextcloud MCP

The Nextcloud MCP server provides high-level tools for contact lifecycle management (search, create, update, delete).

### Usage Examples

1.  **Search Contacts**:
    - Tool: `nextcloud_search_contacts(query="name or email")`
    - Use this to find existing contacts to link in Trac tickets or Google Calendar events.
2.  **Create Contact**:
    - Tool: `nextcloud_create_contact(fn="Full Name", email="user@example.com", tel="555-0199", ...)`
    - This is the primary method for adding new contacts discovered during other tasks (e.g., from an email or a Trac ticket).
3.  **Update Contact**:
    - Tool: `nextcloud_update_contact(uid="UUID", fn="New Name", email="new@example.com", ...)`
    - Note: This tool **appends** new values for multi-value fields (EMAIL, TEL, URL, ADR, CATEGORIES) by default. Use this to enrich existing contact records with new information.
4.  **Delete Contact**:
    - Tool: `nextcloud_delete_contact(uid="UUID")`
    - Only perform deletions when explicitly requested by the user.

## Best Practices

- **UID Management**: Always retrieve the `uid` using `nextcloud_search_contacts` before performing updates or deletions.
- **VCard Standards**: The MCP server handles vCard construction automatically. Ensure fields like `fn` (Full Name) are always provided for new contacts.
- **Integration**: When a new contact is created, consider adding their details (like a link to their Nextcloud entry) into a related Trac ticket or Google Calendar event.
- **SSO/Authentication**: The Nextcloud MCP server relies on the `NEXTCLOUD_PASSWORD` environment variable. If it's not set, it will attempt to fall back to `~/.bashrc` or a vault cache. If it fails, inform the user they need to set the variable.
