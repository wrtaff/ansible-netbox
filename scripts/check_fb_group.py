#!/usr/bin/env python3
"""
================================================================================
Filename:       check_fb_group.py
Version:        1.0
Author:         Antigravity
Last Modified:  2026-06-12
Context:        Facebook Group Updates (EPSC)

Purpose:
    Scrape the EPSC Facebook group using Playwright with the persistent
    profile to check for new posts. If a new post is detected, notify
    via Home Assistant.

Secrets:
    None - no direct credentials required (delegates to hass_api_manager.py)

Revision History:
    v1.0 (2026-06-12) - Initial version.

Usage:
    /opt/venvs/gemini_projects/bin/python3 check_fb_group.py
================================================================================
"""
import os
import sys
import json
import time
import subprocess
from playwright.sync_api import sync_playwright

# Configuration
GROUP_URL = "https://www.facebook.com/groups/473971729877417/"
STATE_FILE = "/home/will/pops/tmp/fb_group_state.json"
PROFILE_DIR = "/home/will/.cache/ms-playwright/mcp-chrome-f96f1ec" # Default Playwright MCP chrome profile
CHROME_PATH = "/usr/bin/google-chrome"

def notify_via_hass(message):
    """Call Home Assistant to post a persistent notification."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    hass_manager = os.path.join(script_dir, "hass_api_manager.py")
    
    payload = {
        "title": "EPSC Facebook Group Update",
        "message": message
    }
    
    try:
        subprocess.run(
            [sys.executable, hass_manager, "call", "persistent_notification", "create", json.dumps(payload)],
            check=True,
            capture_output=True,
            text=True
        )
        print("Notification sent to Home Assistant.")
    except Exception as e:
        print(f"Failed to send Home Assistant notification: {e}", file=sys.stderr)

def main():
    if not os.path.exists(PROFILE_DIR):
        # Fallback to Chrome for testing profile if first profile doesn't exist
        alt_profile = "/home/will/.cache/ms-playwright/mcp-chrome-for-testing-f96f1ec"
        if os.path.exists(alt_profile):
            profile_path = alt_profile
        else:
            print(f"Error: Profile directory {PROFILE_DIR} not found.", file=sys.stderr)
            sys.exit(1)
    else:
        profile_path = PROFILE_DIR

    print(f"Using profile path: {profile_path}")

    # Ensure state directory exists
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    with sync_playwright() as p:
        # Launch using persistent context (headless)
        print("Launching browser context...")
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                executable_path=CHROME_PATH,
                headless=True
            )
        except Exception as e:
            # If browser is locked by a running MCP server, we'll get an error
            print(f"Error launching context. Playwright may be locked by another process: {e}", file=sys.stderr)
            sys.exit(1)

        page = context.new_page()
        
        print(f"Navigating to group URL: {GROUP_URL}")
        page.goto(GROUP_URL, wait_until="networkidle")
        
        # Wait a bit for dynamic posts to load
        page.wait_for_timeout(3000)
        
        # Check if we got redirected to login (session expired)
        if "login" in page.url or page.locator("input[name='email']").first.is_visible():
            print("Session expired or not logged in. Sending notification.")
            notify_via_hass("Facebook session has expired. Please log back in using the Facebook Messenger skill to refresh the session.")
            context.close()
            sys.exit(0)

        # Scrape recent posts
        print("Scraping feed...")
        feed_articles = page.locator('div[role="article"]').all()
        
        posts = []
        for i, article in enumerate(feed_articles[:3]):
            text = article.inner_text().strip()
            if text:
                posts.append(text)

        context.close()

    if not posts:
        print("No posts found. Facebook page layout might have changed or feed failed to load.")
        sys.exit(1)

    latest_post = posts[0]
    print(f"Latest post content preview: {latest_post[:100]}...")

    # Load old state
    old_state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                old_state = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load old state: {e}")

    # Check if latest post is new
    last_known_post = old_state.get("latest_post")
    if last_known_post != latest_post:
        print("New post detected!")
        # Save new state
        with open(STATE_FILE, 'w') as f:
            json.dump({"latest_post": latest_post, "updated_at": time.time()}, f)
        
        # Trigger notification
        notify_via_hass(f"New update on EPSC Facebook Page:\n\n{latest_post}")
    else:
        print("No new posts detected.")

if __name__ == "__main__":
    main()
