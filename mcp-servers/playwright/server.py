#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/playwright/server.py
Version:        1.0
Author:         OpenCode / Gemini CLI
Last Modified:  2026-08-19
Context:        http://trac.gafla.us.com/ticket/4258

Purpose:
    Progressive, lazy-loading Model Context Protocol (MCP) proxy for Playwright.
    Serves tool schemas (<15 MiB resident Python memory) during session initialization,
    deferring launch of the heavy Node/npx @playwright/mcp subprocess until the first
    browser tool call is received.

Secrets:
    None - no external API credentials required.

Usage:
    python3 server.py

Revision History:
    v1.0 (2026-08-19): Initial implementation of progressive lazy-loading
                       Playwright proxy for Trac #4258.
================================================================================
"""
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time

LOG_FILE = "/tmp/playwright_mcp.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    filename=LOG_FILE,
    filemode="a",
)
logger = logging.getLogger("playwright-lazy-proxy")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SCHEMA_FILE = os.path.join(SCRIPT_DIR, "tools_schema.json")


def load_cached_tools():
    if os.path.exists(SCHEMA_FILE):
        try:
            with open(SCHEMA_FILE, "r") as f:
                data = json.load(f)
                return data.get("tools", [])
        except Exception as e:
            logger.error(f"Failed to load schema file: {e}")
    return []


CACHED_TOOLS = load_cached_tools()


class PlaywrightProxy:
    def __init__(self):
        self.child_proc = None
        self.child_thread = None
        self.client_init_params = {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "agent-runner", "version": "1.0"},
        }
        self.lock = threading.Lock()
        self.running = True

    def get_child_command(self):
        browser = os.environ.get("PLAYWRIGHT_BROWSER", "firefox")
        headless = os.environ.get("PLAYWRIGHT_HEADLESS", "true").lower() in (
            "true",
            "1",
            "yes",
        )
        exec_path = os.environ.get("PLAYWRIGHT_EXECUTABLE_PATH", "")
        if not exec_path and browser == "firefox" and os.path.exists("/usr/bin/firefox"):
            exec_path = "/usr/bin/firefox"

        cmd = ["npx", "@playwright/mcp"]
        if headless:
            cmd.append("--headless")
        if browser:
            cmd.extend(["--browser", browser])
        if exec_path and os.path.exists(exec_path):
            cmd.extend(["--executable-path", exec_path])
        return cmd

    def _child_stdout_loop(self):
        logger.info("Started child stdout reader loop")
        try:
            for line in iter(self.child_proc.stdout.readline, ""):
                if not line:
                    break
                sys.stdout.write(line)
                sys.stdout.flush()
        except Exception as e:
            logger.error(f"Error in child stdout loop: {e}")
        finally:
            logger.info("Child stdout reader loop terminated")

    def _child_stderr_loop(self):
        try:
            for line in iter(self.child_proc.stderr.readline, ""):
                if not line:
                    break
                logger.debug(f"[child stderr] {line.strip()}")
        except Exception as e:
            logger.error(f"Error in child stderr loop: {e}")

    def start_child(self):
        with self.lock:
            if self.child_proc and self.child_proc.poll() is None:
                return

            cmd = self.get_child_command()
            logger.info(f"Spawning child Playwright MCP: {' '.join(cmd)}")
            self.child_proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            # Handshake with child
            init_req = {
                "jsonrpc": "2.0",
                "id": "__proxy_init__",
                "method": "initialize",
                "params": self.client_init_params,
            }
            self.child_proc.stdin.write(json.dumps(init_req) + "\n")
            self.child_proc.stdin.flush()

            # Read child init response
            init_res = self.child_proc.stdout.readline()
            logger.info(f"Child init response: {init_res.strip()}")

            # Send initialized notification to child
            init_notif = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            self.child_proc.stdin.write(json.dumps(init_notif) + "\n")
            self.child_proc.stdin.flush()

            # Start background readers
            self.child_thread = threading.Thread(
                target=self._child_stdout_loop, daemon=True
            )
            self.child_thread.start()

            stderr_thread = threading.Thread(
                target=self._child_stderr_loop, daemon=True
            )
            stderr_thread.start()
            logger.info(
                "Child Playwright process successfully initialized and background threads running"
            )

    def stop_child(self):
        with self.lock:
            if self.child_proc and self.child_proc.poll() is None:
                logger.info("Stopping child Playwright MCP process...")
                try:
                    self.child_proc.terminate()
                    self.child_proc.wait(timeout=3)
                except Exception as e:
                    logger.warning(f"Failed to cleanly terminate child, killing: {e}")
                    self.child_proc.kill()
                self.child_proc = None

    def send_response(self, resp_dict):
        line = json.dumps(resp_dict) + "\n"
        sys.stdout.write(line)
        sys.stdout.flush()

    def run(self):
        logger.info("Playwright Proxy starting stdio loop")
        try:
            for raw_line in sys.stdin:
                line = raw_line.strip()
                if not line:
                    continue

                try:
                    msg = json.loads(line)
                except Exception as e:
                    logger.error(f"Invalid JSON from client: {e} | line: {line}")
                    continue

                # If child is already running, transparently forward everything
                if self.child_proc and self.child_proc.poll() is None:
                    try:
                        self.child_proc.stdin.write(
                            raw_line
                            if raw_line.endswith("\n")
                            else raw_line + "\n"
                        )
                        self.child_proc.stdin.flush()
                    except Exception as e:
                        logger.error(f"Failed to forward message to child: {e}")
                    continue

                # Child is NOT running: intercept lazy methods
                msg_id = msg.get("id")
                method = msg.get("method")

                if method == "initialize":
                    if "params" in msg and isinstance(msg["params"], dict):
                        self.client_init_params = msg["params"]
                    self.send_response({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "protocolVersion": "2024-11-05",
                            "capabilities": {
                                "tools": {"listChanged": False}
                            },
                            "serverInfo": {
                                "name": "Playwright",
                                "version": "1.0 (Lazy Proxy)",
                            },
                        },
                    })
                elif method == "notifications/initialized":
                    logger.info("Received notifications/initialized from client")
                elif method == "ping":
                    self.send_response({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {},
                    })
                elif method == "tools/list":
                    logger.info("Serving cached tools/list without starting child")
                    self.send_response({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "tools": CACHED_TOOLS
                        },
                    })
                elif method == "tools/call" or (
                    method and not method.startswith("notifications/")
                ):
                    logger.info(
                        f"Intercepted {method} request ({msg.get('params', {}).get('name')}). Starting child on demand!"
                    )
                    self.start_child()
                    # Forward the request to newly spawned child
                    self.child_proc.stdin.write(
                        raw_line
                        if raw_line.endswith("\n")
                        else raw_line + "\n"
                    )
                    self.child_proc.stdin.flush()
                else:
                    logger.debug(f"Unhandled notification/message while idle: {method}")

        except KeyboardInterrupt:
            pass
        finally:
            logger.info("Parent stdin closed or loop ended. Cleaning up.")
            self.stop_child()


if __name__ == "__main__":
    proxy = PlaywrightProxy()
    proxy.run()
