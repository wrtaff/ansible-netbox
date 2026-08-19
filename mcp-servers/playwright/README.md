# Playwright Lazy Proxy MCP Server

This is a progressive, lazy-loading Model Context Protocol (MCP) server proxy for Playwright browser automation.

## Purpose

Standard `@playwright/mcp` starts a resident Node.js/npm runtime consuming ~180-200 MiB of RAM per configured instance. When multiple Playwright instances are configured or multiple agent sessions run, memory overhead quickly multiplies.

This proxy provides:
1. **Zero Idle Node Overhead**: Immediately serves MCP `initialize`, `ping`, and cached `tools/list` responses from a lightweight Python process (<15 MiB resident memory).
2. **On-Demand Subprocess Spawning**: Spawns `@playwright/mcp` only when an actual browser tool call (e.g. `browser_navigate`, `browser_click`) is dispatched.
3. **Transparent JSON-RPC Bridging**: Seamlessly pipes all requests and responses once the child process is active.
4. **Clean Session Teardown**: Automatically terminates the child browser process when the parent MCP client disconnects.

## Environment Variables

* `PLAYWRIGHT_BROWSER`: Target browser engine (`firefox` [default], `chromium`, `webkit`, `chrome`).
* `PLAYWRIGHT_HEADLESS`: Whether to run in headless mode (`true` [default] or `false`).
* `PLAYWRIGHT_EXECUTABLE_PATH`: Custom browser executable path (e.g., `/usr/bin/firefox`).
