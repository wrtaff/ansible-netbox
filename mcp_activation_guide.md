# Activating MCP Servers in OpenCode TUI

## Overview
MCP (Model Context Protocol) servers provide tools to interact with external systems (like Trac) from within the OpenCode interface.

## For Your Existing Trac MCP Server

Your Trac MCP server is located at:
`/home/will/ansible-netbox/mcp-servers/trac/`

### Prerequisite: Start the Trac Server
First, you need to run the Trac server as a standalone process:

```bash
cd /home/will/ansible-netbox/mcp-servers/trac/
export TRAC_PASSWORD="your_password"
python server.py
```

### Available Tools
The Trac server provides these tools:
- `get_ticket(ticket_id)`: View ticket details
- `update_ticket(ticket_id, comment, ...)`: Add comments or change status/keywords/priority
- `create_ticket(summary, description, ...)`: Open a new ticket
- `search_tickets(query)`: Search using Trac query syntax

**Note:** Trac components are always lowercase in this implementation.

## For Your New NetBox MCP Server

Your NetBox MCP server is located at:
`/home/will/ansible-netbox/mcp-servers/netbox/`

### Prerequisite: Start the NetBox Server
First, you need to run the NetBox server as a standalone process:

```bash
cd /home/will/ansible-netbox/mcp-servers/netbox/
export NETBOX_TOKEN="your_token"
python server.py
```

### Available Tools
The NetBox server provides these tools:
- `netbox_ping()`: Test connectivity to NetBox.
- `netbox_get_vm(name)`: Retrieve full details for a Virtual Machine by name.
- `netbox_get_device(name)`: Retrieve full details for a physical Device by name.
- `netbox_search_vms(query)`: Search for Virtual Machines using a query string.
- `netbox_search_devices(query)`: Search for physical Devices using a query string.
- `netbox_update_vm(name, ...)`: Update fields on a Virtual Machine.
- `netbox_update_device(name, ...)`: Update fields on a physical Device.
- `netbox_get_interfaces(device_name/vm_name)`: Retrieve interfaces.
- `netbox_get_ip_addresses(query/device_name/vm_name)`: Retrieve IP addresses.
- `netbox_get_services(device_name/vm_name)`: Retrieve services.

## General MCP Server Activation Steps

1. **MCP Server Execution**:  
   MCP servers typically run as standalone processes that communicate via standard input/output (stdio).

2. **OpenCode Connection**:  
   OpenCode CLI tools connect to MCP servers via stdio transport or network sockets.

3. **Configuration**:  
   Check for OpenCode configuration files:
   - `.opencode/config.yaml` or similar in your home directory
   - `~/.config/opencode/` configuration directory
   - Project-specific configuration files

4. **Typical Configuration Pattern**:  
   ```yaml
   mcp_servers:
     trac:
       command: "python"
       args: ["/home/will/ansible-netbox/mcp-servers/trac/server.py"]
       env:
         TRAC_PASSWORD: "${TRAC_PASSWORD}"
   ```

5. **Restart Required**:  
   Restart OpenCode after adding new MCP server configurations.

## How to Use Once Activated

Once properly configured, you can use commands like:
- `@mcp-servers/trac/ get_ticket #3285`
- `@mcp-servers/trac/ search_tickets "status!=closed"`

## Next Steps

1. Check OpenCode documentation at `opencode.ai/docs` for exact configuration syntax
2. Look for existing MCP server configurations in your OpenCode setup
3. Test the Trac server standalone first to ensure it works
4. Add the server to OpenCode's configuration
5. Restart OpenCode and test with a simple command

## Troubleshooting

- If the server isn't available, ensure it's running and accessible
- Check that environment variables are properly set
- Verify the Python script has execute permissions
- Look for error messages in the server's output
- Check OpenCode logs for connection issues