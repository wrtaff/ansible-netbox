# Trac MCP Server

This is a Model Context Protocol (MCP) server that provides tools to interact with the local Trac instance.

## Usage

You can run this server using `python` directly or via an MCP client.

### Environment Variables

*   `TRAC_PASSWORD`: The password for the `gemini` user (defaulting to standard infrastructure password).

### Running

```bash
export TRAC_PASSWORD="your_password"
python server.py
```

## Tools

*   `get_ticket(ticket_id)`: View ticket details.
*   `update_ticket(ticket_id, comment, ...)`: Add comments or change status/keywords.
*   `create_ticket(summary, description, ...)`: Open a new ticket.
*   `search_tickets(query)`: Search using Trac query syntax.
