#!/usr/bin/env python3
"""Run a stdio-only FastMCP server (trac/wwos/vikunja/...) as an SSE endpoint.

Each server module exposes a module-level `mcp = FastMCP("...")` instance and
calls `mcp.run()` (stdio) under `if __name__ == "__main__":`. FastMCP's SSE
transport binds to 127.0.0.1 by default and enables DNS-rebinding protection
locked to localhost/127.0.0.1/::1, so a plain host="0.0.0.0" override alone
still returns HTTP 421 for LAN clients. This wrapper imports the target
module without triggering its __main__ block, rewrites `mcp.settings` in
place (host, port, and the allowed transport-security hosts/origins), and
then runs the SSE transport directly -- avoiding CLI flags that don't map
onto FastMCP 2.x's constructor-only host/port/transport_security kwargs.

Usage:
    sse_runner.py <path/to/server.py> <port> <allowed_host_1> [<allowed_host_2> ...]

Example (matches the systemd units under playbooks/templates/mcp-sse.service.j2):
    sse_runner.py mcp-servers/trac/server.py 8091 192.168.0.186 192.168.0.114
"""

import importlib.util
import sys


def load_server_module(server_path: str):
    spec = importlib.util.spec_from_file_location("mcp_target_server", server_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <server.py> <port> <allowed_host> [<allowed_host> ...]", file=sys.stderr)
        raise SystemExit(2)

    server_path = sys.argv[1]
    port = int(sys.argv[2])
    allowed_hosts = sys.argv[3:]

    module = load_server_module(server_path)
    mcp = module.mcp

    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port

    host_patterns = [f"{h}:*" for h in allowed_hosts] + ["127.0.0.1:*", "localhost:*", "[::1]:*"]
    origin_patterns = [f"http://{h}:*" for h in allowed_hosts] + [
        "http://127.0.0.1:*",
        "http://localhost:*",
        "http://[::1]:*",
    ]
    mcp.settings.transport_security.allowed_hosts = host_patterns
    mcp.settings.transport_security.allowed_origins = origin_patterns

    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
