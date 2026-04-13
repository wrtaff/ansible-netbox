# NetBox MCP Server

Model Context Protocol (MCP) server for NetBox integration.
Provides tools for device and virtual machine management within AI agent sessions.

## Features
- **netbox_ping**: Test connectivity to NetBox.
- **netbox_get_vm**: Retrieve full details for a Virtual Machine by name.
- **netbox_get_device**: Retrieve full details for a physical Device by name.
- **netbox_search_vms**: Search for Virtual Machines using a query string.
- **netbox_search_devices**: Search for physical Devices using a query string.
- **netbox_update_vm**: Update fields (like comments) on a Virtual Machine.
- **netbox_update_device**: Update fields (like comments) on a physical Device.

## Configuration
Requires `NETBOX_TOKEN` environment variable or defined in `~/.bashrc`.
Default URL: `http://netbox1.home.arpa`
