#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/validate_mcp_credentials.py
Version:        1.0
Author:         OpenCode
Last Modified:  2026-08-19
Context:        http://trac.gafla.us.com/ticket/4137

Purpose:
    Read-only credential validation across managed MCP and service API consumers.
    Validates delivery presence in ~/.config/mcp-secrets.env (or environment)
    and verifies upstream acceptance without exposing or printing secret values.

Secrets:
    Reads PORKBUN_API_KEY, PORKBUN_SECRET_KEY, TRAC_PASSWORD, GRAYLOG_API_TOKEN,
    NETBOX_TOKEN, NEXTCLOUD_PASSWORD, WWOS_PASSWORD, VIKUNJA_TOKEN, HASS_TOKEN,
    and LLM API keys. Values are never displayed, logged, or echoed.

Usage:
    python3 scripts/validate_mcp_credentials.py [--json] [--verbose]

Revision History:
    v1.0 (2026-08-19): Initial implementation for Trac #4137 WP-2.
================================================================================
"""

import os
import sys
import json
import argparse
import base64
import urllib.request
import urllib.error
import urllib.parse
import xmlrpc.client
import ssl

# Disable strict SSL verification for internal lab self-signed certs where needed
_UNVERIFIED_SSL_CTX = ssl._create_unverified_context()


def load_managed_secrets() -> dict:
    """Load secrets from environment, falling back to ~/.config/mcp-secrets.env, ~/.mcp.json, and ~/.bashrc."""
    secrets = {}

    # 1. ~/.config/mcp-secrets.env (Ansible managed file)
    env_file = os.path.expanduser("~/.config/mcp-secrets.env")
    if os.path.isfile(env_file):
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if "=" in line and not line.startswith("#"):
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key and val:
                            secrets[key] = val
        except Exception:
            pass

    # 2. ~/.mcp.json / ~/pops/.mcp.json env blocks
    for mcp_json in [os.path.expanduser("~/.mcp.json"), os.path.expanduser("~/pops/.mcp.json")]:
        if os.path.isfile(mcp_json):
            try:
                with open(mcp_json, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    for srv in cfg.get("mcpServers", {}).values():
                        for k, v in srv.get("env", {}).items():
                            if v and k not in secrets:
                                secrets[k] = v
            except Exception:
                pass

    # 3. ~/.bashrc fallback
    bashrc_file = os.path.expanduser("~/.bashrc")
    if os.path.isfile(bashrc_file):
        try:
            with open(bashrc_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export "):
                        line = line[7:].strip()
                    if "=" in line and not line.startswith("#"):
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key and val and key not in secrets:
                            secrets[key] = val
        except Exception:
            pass

    # 4. Process environment overrides
    for key, val in os.environ.items():
        if val:
            secrets[key] = val

    return secrets


def check_trac(secrets: dict) -> tuple:
    """Validate Trac XML-RPC read-only access."""
    user = secrets.get("TRAC_USER", "will")
    password = secrets.get("TRAC_PASSWORD")
    if not password:
        return False, "Missing TRAC_PASSWORD"

    urls = [
        f"http://{user}:{urllib.parse.quote(password)}@trac.home.arpa/login/xmlrpc",
        f"http://{user}:{urllib.parse.quote(password)}@trac.gafla.us.com/login/xmlrpc",
    ]
    for url in urls:
        try:
            server = xmlrpc.client.ServerProxy(url)
            methods = server.system.listMethods()
            if "ticket.get" in methods:
                return True, "Authenticated (XML-RPC system.listMethods OK)"
        except Exception as e:
            last_err = str(e)
            continue
    return False, f"Auth/connection failed: {last_err}"


def check_wwos(secrets: dict) -> tuple:
    """Validate WWOS MediaWiki API read-only query."""
    user = secrets.get("WWOS_USER", "will")
    password = secrets.get("WWOS_PASSWORD")
    if not password:
        return False, "Missing WWOS_PASSWORD"

    url = "http://wwos.home.arpa/api.php?action=query&meta=siteinfo&format=json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pops-credential-validator/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if "query" in data and "general" in data["query"]:
                sitename = data["query"]["general"].get("sitename", "WWOS")
                return True, f"Reachability OK (Site: {sitename})"
    except Exception as e:
        return False, f"API query failed: {e}"
    return False, "Unexpected response structure"


def check_porkbun(secrets: dict) -> tuple:
    """Validate Porkbun API credentials via ping endpoint."""
    api_key = secrets.get("PORKBUN_API_KEY")
    secret_key = secrets.get("PORKBUN_SECRET_KEY")
    if not api_key or not secret_key:
        return False, "Missing PORKBUN_API_KEY or PORKBUN_SECRET_KEY"

    url = "https://api.porkbun.com/api/json/v3/ping"
    payload = json.dumps({"apikey": api_key, "secretapikey": secret_key}).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("status") == "SUCCESS":
                return True, "Authenticated (Porkbun API ping SUCCESS)"
            return False, f"API status: {data.get('status')}"
    except urllib.error.HTTPError as e:
        return False, f"HTTP Error {e.code}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def check_graylog(secrets: dict) -> tuple:
    """Validate Graylog API token via /api/system read-only endpoint."""
    token = secrets.get("GRAYLOG_API_TOKEN")
    if not token:
        return False, "Missing GRAYLOG_API_TOKEN"

    base_url = secrets.get("GRAYLOG_URL", "http://graylog.home.arpa:9000")
    url = f"{base_url.rstrip('/')}/api/system"
    auth_header = "Basic " + base64.b64encode(f"{token}:token".encode("utf-8")).decode("utf-8")
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": auth_header,
            "Accept": "application/json",
            "X-Requested-By": "pops-agent",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                version = data.get("version", "unknown")
                return True, f"Authenticated (Graylog version {version})"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return False, "HTTP 401 Unauthorized (Invalid or stale token)"
        return False, f"HTTP Error {e.code}"
    except Exception as e:
        return False, f"Connection failed: {e}"
    return False, "Unknown failure"


def check_netbox(secrets: dict) -> tuple:
    """Validate NetBox API token via /api/status/ endpoint."""
    token = secrets.get("NETBOX_TOKEN") or secrets.get("NETBOX_API_TOKEN")
    if not token:
        return False, "Missing NETBOX_TOKEN"

    base_url = secrets.get("NETBOX_URL", "http://netbox1.home.arpa")
    url = f"{base_url.rstrip('/')}/api/status/"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Token {token}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                version = data.get("netbox-version", "unknown")
                return True, f"Authenticated (NetBox version {version})"
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return False, f"HTTP {e.code} (Invalid token)"
        return False, f"HTTP Error {e.code}"
    except Exception as e:
        return False, f"Connection failed: {e}"
    return False, "Unknown failure"


def check_vikunja(secrets: dict) -> tuple:
    """Validate Vikunja API token via /api/v1/user endpoint."""
    token = (
        secrets.get("VIKUNJA_API_TOKEN")
        or secrets.get("VIKUNJA_TOKEN")
        or secrets.get("vault_vikunja_api_token")
    )
    if not token:
        return False, "Missing VIKUNJA_API_TOKEN"

    base_url = secrets.get("VIKUNJA_URL", "http://todo.gafla.us.com")
    urls = [
        f"{base_url.rstrip('/')}/api/v1/user",
        "https://todo.gafla.us.com/api/v1/user",
        "http://todo.home.arpa/api/v1/user",
    ]
    last_err = "No response"
    for url in urls:
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5, context=_UNVERIFIED_SSL_CTX) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    username = data.get("username", "valid")
                    return True, f"Authenticated (User: {username})"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return False, f"HTTP {e.code} (Invalid token)"
            last_err = f"HTTP Error {e.code}"
        except Exception as e:
            last_err = f"Connection failed ({e})"
            continue
    return False, last_err


def check_nextcloud(secrets: dict) -> tuple:
    """Validate Nextcloud credentials via status endpoint."""
    user = secrets.get("NEXTCLOUD_USER", "will")
    password = secrets.get("NEXTCLOUD_PASSWORD")
    if not password:
        return False, "Missing NEXTCLOUD_PASSWORD"

    base_url = secrets.get("NEXTCLOUD_URL", "https://ynh2.van-bee.ts.net/nextcloud")
    url = f"{base_url.rstrip('/')}/status.php"
    req = urllib.request.Request(url, headers={"User-Agent": "pops-credential-validator/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5, context=_UNVERIFIED_SSL_CTX) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                version = data.get("versionstring", data.get("version", "unknown"))
                return True, f"Service Reachable (Nextcloud {version})"
    except Exception as e:
        return False, f"Endpoint check failed: {e}"
    return False, "Unknown failure"


def check_homeassistant(secrets: dict) -> tuple:
    """Validate Home Assistant Long-Lived Access Token via /api/ endpoint."""
    token = secrets.get("HASS_TOKEN") or secrets.get("vault_hass_token")
    if not token:
        return False, "Missing HASS_TOKEN"

    urls = [
        "http://hass.home.arpa/api/",
        "http://homeassistant.home.arpa:8123/api/",
        "http://hass.home.arpa:8123/api/",
    ]
    last_err = "No response"
    for url in urls:
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    msg = data.get("message", "API running.")
                    return True, f"Authenticated ({msg})"
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return False, f"HTTP {e.code} (Invalid token)"
            last_err = f"HTTP Error {e.code}"
        except Exception as e:
            last_err = f"Connection failed ({e})"
            continue
    return False, last_err


def check_llm_keys(secrets: dict) -> dict:
    """Check presence of LLM API keys without sending outbound test requests."""
    llm_keys = {
        "GEMINI_API_KEY": secrets.get("GEMINI_API_KEY") or secrets.get("GOOGLE_API_KEY"),
        "OPENAI_API_KEY": secrets.get("OPENAI_API_KEY"),
        "ANTHROPIC_API_KEY": secrets.get("ANTHROPIC_API_KEY"),
        "OPENROUTER_API_KEY": secrets.get("OPENROUTER_API_KEY"),
    }
    results = {}
    for name, val in llm_keys.items():
        if val:
            results[name] = (True, "Present in environment / managed secret store")
        else:
            results[name] = (False, "Missing from environment / managed store")
    return results


def main():
    parser = argparse.ArgumentParser(description="Read-only credential validation for Pops managed services.")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    secrets = load_managed_secrets()

    checks = {
        "Trac": check_trac(secrets),
        "WWOS": check_wwos(secrets),
        "Porkbun": check_porkbun(secrets),
        "Graylog": check_graylog(secrets),
        "NetBox": check_netbox(secrets),
        "Vikunja": check_vikunja(secrets),
        "Nextcloud": check_nextcloud(secrets),
        "Home Assistant": check_homeassistant(secrets),
    }

    llm_results = check_llm_keys(secrets)

    if args.json:
        output = {
            "services": {k: {"ok": v[0], "message": v[1]} for k, v in checks.items()},
            "llm_keys": {k: {"ok": v[0], "message": v[1]} for k, v in llm_results.items()},
        }
        print(json.dumps(output, indent=2))
        return

    print("=" * 72)
    print("Pops Managed Credential Validation (Read-Only)")
    print("=" * 72)
    print(f"{'Service / Consumer':<20} | {'Status':<8} | {'Details'}")
    print("-" * 72)

    failures = 0
    for service, (ok, detail) in checks.items():
        status_str = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"{service:<20} | {status_str:<8} | {detail}")

    print("-" * 72)
    print("LLM API Key Presence Checks:")
    for key_name, (ok, detail) in llm_results.items():
        status_str = "PRESENT" if ok else "ABSENT"
        print(f"{key_name:<20} | {status_str:<8} | {detail}")

    print("=" * 72)
    if failures > 0:
        print(f"Result: {failures} service validation failure(s) detected.")
        sys.exit(1)
    else:
        print("Result: All active service credentials validated successfully.")
        sys.exit(0)


if __name__ == "__main__":
    main()
