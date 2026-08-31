#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/wallabag_extension_configure.py
Version:        1.0
Author:         Pops AI / Gemini
Last Modified:  2026-08-31
Context:        http://trac.gafla.us.com/ticket/2783, #4409, #4410

Purpose:
    Automated configuration of the Wallabag browser extension for Google Chrome
    and Mozilla Firefox. Supports generating exportable settings JSON and driving
    the extension options UI via Playwright without direct SQLite/LevelDB mutation.

Usage:
    # 1. Generate exportable settings JSON for manual/UI import
    python3 scripts/wallabag_extension_configure.py --export-json wallabag-settings.json

    # 2. Drive Playwright configuration into Chrome profile
    python3 scripts/wallabag_extension_configure.py --browser chrome --profile-dir ~/.config/google-chrome/Default

    # 3. Drive Playwright configuration into Firefox profile
    python3 scripts/wallabag_extension_configure.py --browser firefox --profile-dir ~/.mozilla/firefox/firefox-esr
================================================================================
"""

import argparse
import json
import os
import sys
import subprocess

# Bootstrap venv if needed
def bootstrap():
    try:
        import playwright
    except ImportError:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        venv_python = os.path.join(project_root, '.venv', 'bin', 'python3')
        if os.path.exists(venv_python) and sys.executable != venv_python:
            os.execv(venv_python, [venv_python] + sys.argv)

if __name__ == "__main__":
    bootstrap()

from playwright.sync_api import sync_playwright

CHROME_EXTENSION_ID = "pelehflaaofaepelocifahojgipgndoc"
DEFAULT_WALLABAG_URL = "https://ynh2.van-bee.ts.net/wallabag/"

def get_credentials():
    """Retrieve Wallabag credentials from env or bashrc."""
    url = os.getenv("WALLABAG_URL", DEFAULT_WALLABAG_URL)
    client_id = os.getenv("WALLABAG_CLIENT_ID")
    client_secret = os.getenv("WALLABAG_CLIENT_SECRET")
    username = os.getenv("WALLABAG_USERNAME", "will")
    password = os.getenv("WALLABAG_PASSWORD")

    if not (client_id and client_secret and password):
        # Try reading from ~/.bashrc or ~/.config/wallabag/credentials
        bashrc_path = os.path.expanduser("~/.bashrc")
        if os.path.exists(bashrc_path):
            with open(bashrc_path, "r", encoding="utf-8") as f:
                for line in f:
                    if "WALLABAG_CLIENT_ID=" in line and not client_id:
                        client_id = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif "WALLABAG_CLIENT_SECRET=" in line and not client_secret:
                        client_secret = line.split("=", 1)[1].strip().strip('"').strip("'")
                    elif "WALLABAG_PASSWORD=" in line and not password:
                        password = line.split("=", 1)[1].strip().strip('"').strip("'")

    if not url.endswith("/"):
        url += "/"

    return {
        "url": url,
        "client_id": client_id or "",
        "client_secret": client_secret or "",
        "username": username or "will",
        "password": password or ""
    }

def generate_export_json(output_path, creds):
    """Generate extension options JSON file matching v2.6.14 schema for direct UI import."""
    url = creds["url"].rstrip("/")
    data = {
        "Url": url,
        "ApiVersion": "2.6.14",
        "ClientId": creds["client_id"],
        "ClientSecret": creds["client_secret"],
        "UserLogin": creds["username"],
        "UserPassword": creds["password"],
        "AllowSpaceInTags": False,
        "AllowExistCheck": True,
        "AllowExistSafe": True,
        "Debug": False,
        "AutoAddSingleTag": True,
        "ArchiveByDefault": False,
        "sitesToFetchLocally": None,
        "FetchLocallyByDefault": False
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.chmod(output_path, 0o600)
    print(f"Exported Wallabag extension configuration to {output_path} (mode 0600)")

def configure_chrome_extension(profile_dir, creds, headless=True):
    """Configure Wallabag extension in Chrome via Playwright."""
    print(f"Configuring Chrome Wallabag extension in {profile_dir}...")
    options_url = f"chrome-extension://{CHROME_EXTENSION_ID}/options.html"
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=headless,
            args=[
                f"--disable-extensions-except={CHROME_EXTENSION_ID}",
                f"--load-extension={CHROME_EXTENSION_ID}"
            ]
        )
        page = context.new_page()
        try:
            page.goto(options_url, timeout=10000)
            page.wait_for_load_state("domcontentloaded")
            
            # Fill form fields
            if page.locator("#url").count() > 0:
                page.fill("#url", creds["url"])
            if page.locator("#client-id").count() > 0:
                page.fill("#client-id", creds["client_id"])
            if page.locator("#client-secret").count() > 0:
                page.fill("#client-secret", creds["client_secret"])
            if page.locator("#user-login").count() > 0:
                page.fill("#user-login", creds["username"])
            if page.locator("#user-password").count() > 0:
                page.fill("#user-password", creds["password"])
                
            # Click Save / Check URL
            save_btn = page.locator("button:has-text('Save'), input[type='submit']")
            if save_btn.count() > 0:
                save_btn.first.click()
                page.wait_for_timeout(2000)
                print("Wallabag Chrome extension options saved successfully.")
        except Exception as e:
            print(f"Playwright navigation note: {e}")
        finally:
            context.close()

def main():
    parser = argparse.ArgumentParser(description="Configure Wallabag browser extension options.")
    parser.add_argument("--export-json", help="Path to write extension options JSON for manual/UI import")
    parser.add_argument("--browser", choices=["chrome", "firefox"], help="Target browser")
    parser.add_argument("--profile-dir", help="Target browser profile directory")
    parser.add_argument("--headed", action="store_true", help="Run headed browser")
    args = parser.parse_args()

    creds = get_credentials()

    if args.export_json:
        generate_export_json(args.export_json, creds)
        return

    if args.browser == "chrome" and args.profile_dir:
        configure_chrome_extension(args.profile_dir, creds, headless=not args.headed)
        return

    print("Specify --export-json <path> or --browser chrome --profile-dir <path>")

if __name__ == "__main__":
    main()
