# Vikunja MCP Server

This is a Model Context Protocol (MCP) server that provides tools to interact with the local Vikunja instance and link tasks to Trac tickets.

## Usage

This server can be run directly using `python` or via an MCP client.

### Environment Variables

*   `VIKUNJA_API_TOKEN`: The API token for the Vikunja instance.
*   `VIKUNJA_URL`: The URL of the Vikunja instance (Default: `http://todo.home.arpa`).
*   `TRAC_PASSWORD`: Required for tools that link tasks to Trac tickets.

### Running

```bash
export VIKUNJA_API_TOKEN="tk_..."
export TRAC_PASSWORD="your_password"
python server.py
```

## Tools

*   `vikunja_ping()`: Verify connectivity.
*   `vikunja_create_task(title, description, ...)`: Create a new task in Vikunja.
*   `vikunja_get_task(task_id)`: Fetch details of a Vikunja task.
*   `vikunja_list_labels()`: List all available labels.
*   `vikunja_create_trac_ticket(task_id, ...)`: Create a Trac ticket from a Vikunja task and link them.

## Links

*   **WWOS Documentation:** [[Mcp-servers/vikunja]]
*   **Trac Ticket:** [http://trac.home.arpa/ticket/3321 #3321: Develop Vikunja MCP Server Integration]
