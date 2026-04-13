#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/netbox/server.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-04-12
Purpose:
    Model Context Protocol (MCP) server for NetBox integration.
    Provides tools for NetBox device and VM management directly within
    AI agent sessions.
================================================================================
"""
import os
import logging
import pynetbox
from typing import Optional, Dict, Any, List
from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/netbox_mcp.log',
    filemode='a'
)
logger = logging.getLogger("netbox-mcp")

# NetBox Configuration
NETBOX_URL = "http://netbox1.home.arpa"

def get_netbox_token():
    """Gets the NETBOX_TOKEN, falling back to ~/.bashrc if not set in environment."""
    token = os.getenv("NETBOX_TOKEN")
    if token:
        logger.info("NETBOX_TOKEN found in environment.")
        return token

    bashrc_path = os.path.expanduser("~/.bashrc")
    if os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "r") as f:
                for line in f:
                    if "export NETBOX_TOKEN=" in line:
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip('"').strip("'")
                            logger.info("NETBOX_TOKEN found in ~/.bashrc.")
                            return val
        except Exception as e:
            logger.error(f"Error reading ~/.bashrc: {e}")
    
    logger.warning("NETBOX_TOKEN not found.")
    return None

NETBOX_TOKEN = get_netbox_token()

# Initialize FastMCP server
mcp = FastMCP("netbox-server")

def get_nb():
    """Initialize and return a pynetbox API object."""
    if not NETBOX_TOKEN:
        logger.error("Attempted to initialize NetBox without NETBOX_TOKEN.")
        raise ValueError("NETBOX_TOKEN is not set")
    
    nb = pynetbox.api(NETBOX_URL, token=NETBOX_TOKEN)
    # Disable SSL verification for internal NetBox if needed
    # nb.http_session.verify = False 
    return nb

@mcp.tool(name="netbox_ping")
def ping() -> str:
    """Test connectivity to NetBox."""
    try:
        nb = get_nb()
        # Simple status check
        status = nb.status()
        return f"Connected to NetBox {status.get('netbox-version')}"
    except Exception as e:
        logger.error(f"Ping failed: {e}")
        return f"Ping failed: {str(e)}"

@mcp.tool(name="netbox_get_vm")
def get_vm(name: str) -> Optional[Dict[str, Any]]:
    """Retrieve full details for a Virtual Machine by name."""
    try:
        nb = get_nb()
        vm = nb.virtualization.virtual_machines.get(name=name)
        if vm:
            # Convert record to dict for JSON serialization
            return dict(vm)
        return None
    except Exception as e:
        logger.error(f"Failed to get VM '{name}': {e}")
        return {"error": str(e)}

@mcp.tool(name="netbox_get_device")
def get_device(name: str) -> Optional[Dict[str, Any]]:
    """Retrieve full details for a physical Device by name."""
    try:
        nb = get_nb()
        device = nb.dcim.devices.get(name=name)
        if device:
            return dict(device)
        return None
    except Exception as e:
        logger.error(f"Failed to get device '{name}': {e}")
        return {"error": str(e)}

@mcp.tool(name="netbox_search_vms")
def search_vms(query: str) -> List[Dict[str, Any]]:
    """Search for Virtual Machines using a query string."""
    try:
        nb = get_nb()
        vms = nb.virtualization.virtual_machines.filter(q=query)
        return [dict(vm) for vm in vms]
    except Exception as e:
        logger.error(f"VM search failed for '{query}': {e}")
        return [{"error": str(e)}]

@mcp.tool(name="netbox_search_devices")
def search_devices(query: str) -> List[Dict[str, Any]]:
    """Search for physical Devices using a query string."""
    try:
        nb = get_nb()
        devices = nb.dcim.devices.filter(q=query)
        return [dict(dev) for dev in devices]
    except Exception as e:
        logger.error(f"Device search failed for '{query}': {e}")
        return [{"error": str(e)}]

@mcp.tool(name="netbox_update_vm")
def update_vm(name: str, **kwargs) -> Dict[str, Any]:
    """Update fields on a Virtual Machine by name."""
    try:
        nb = get_nb()
        vm = nb.virtualization.virtual_machines.get(name=name)
        if not vm:
            return {"error": f"VM '{name}' not found"}
        
        vm.update(kwargs)
        return dict(vm)
    except Exception as e:
        logger.error(f"Failed to update VM '{name}': {e}")
        return {"error": str(e)}

@mcp.tool(name="netbox_update_device")
def update_device(name: str, **kwargs) -> Dict[str, Any]:
    """Update fields on a physical Device by name."""
    try:
        nb = get_nb()
        device = nb.dcim.devices.get(name=name)
        if not device:
            return {"error": f"Device '{name}' not found"}
        
        device.update(kwargs)
        return dict(device)
    except Exception as e:
        logger.error(f"Failed to update device '{name}': {e}")
        return {"error": str(e)}

@mcp.tool(name="netbox_get_interfaces")
def get_interfaces(device_name: Optional[str] = None, vm_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve interfaces for a physical Device OR a Virtual Machine."""
    try:
        nb = get_nb()
        if device_name:
            device = nb.dcim.devices.get(name=device_name)
            if not device:
                return [{"error": f"Device '{device_name}' not found"}]
            interfaces = nb.dcim.interfaces.filter(device_id=device.id)
            return [dict(iface) for iface in interfaces]
        elif vm_name:
            vm = nb.virtualization.virtual_machines.get(name=vm_name)
            if not vm:
                return [{"error": f"VM '{vm_name}' not found"}]
            interfaces = nb.virtualization.interfaces.filter(virtual_machine_id=vm.id)
            return [dict(iface) for iface in interfaces]
        else:
            return [{"error": "Either device_name or vm_name must be provided"}]
    except Exception as e:
        logger.error(f"Failed to get interfaces: {e}")
        return [{"error": str(e)}]

@mcp.tool(name="netbox_get_ip_addresses")
def get_ip_addresses(query: Optional[str] = None, device_name: Optional[str] = None, vm_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve IP addresses. Filter by query, device name, or VM name."""
    try:
        nb = get_nb()
        if device_name:
            device = nb.dcim.devices.get(name=device_name)
            if not device:
                return [{"error": f"Device '{device_name}' not found"}]
            # There is no direct filter for device name in IP addresses, we need to filter by device_id via interfaces
            ips = nb.ipam.ip_addresses.filter(device_id=device.id)
            return [dict(ip) for ip in ips]
        elif vm_name:
            vm = nb.virtualization.virtual_machines.get(name=vm_name)
            if not vm:
                return [{"error": f"VM '{vm_name}' not found"}]
            ips = nb.ipam.ip_addresses.filter(virtual_machine_id=vm.id)
            return [dict(ip) for ip in ips]
        elif query:
            ips = nb.ipam.ip_addresses.filter(q=query)
            return [dict(ip) for ip in ips]
        else:
            return [{"error": "One of query, device_name, or vm_name must be provided"}]
    except Exception as e:
        logger.error(f"Failed to get IP addresses: {e}")
        return [{"error": str(e)}]

@mcp.tool(name="netbox_get_services")
def get_services(device_name: Optional[str] = None, vm_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve services for a physical Device OR a Virtual Machine."""
    try:
        nb = get_nb()
        if device_name:
            device = nb.dcim.devices.get(name=device_name)
            if not device:
                return [{"error": f"Device '{device_name}' not found"}]
            services = nb.ipam.services.filter(device_id=device.id)
            return [dict(srv) for srv in services]
        elif vm_name:
            vm = nb.virtualization.virtual_machines.get(name=vm_name)
            if not vm:
                return [{"error": f"VM '{vm_name}' not found"}]
            services = nb.ipam.services.filter(virtual_machine_id=vm.id)
            return [dict(srv) for srv in services]
        else:
            return [{"error": "Either device_name or vm_name must be provided"}]
    except Exception as e:
        logger.error(f"Failed to get services: {e}")
        return [{"error": str(e)}]

if __name__ == "__main__":
    mcp.run()
