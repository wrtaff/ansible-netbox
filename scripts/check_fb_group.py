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
PROFILE_DIR = "/home/will/.cache/ms-playwright/mcp-chrome-for-testing-f96f1ec" # Default Playwright MCP chrome profile
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
        # Fallback to standard Chrome profile if testing one doesn't exist
        alt_profile = "/home/will/.cache/ms-playwright/mcp-chrome-f96f1ec"
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
        page.goto(GROUP_URL, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(5000)
        
        # Check if we got redirected to login (session expired)
        if "login" in page.url or page.locator("input[name='email']").first.is_visible():
            print("Session expired or not logged in. Sending notification.")
            notify_via_hass("Facebook session has expired. Please log back in using the Facebook Messenger skill to refresh the session.")
            context.close()
            sys.exit(0)

        # Click the sorting dropdown to select 'New posts'
        print("Checking sort option...")
        sort_btn = page.locator('div[role="button"]:has-text("Most relevant")').first
        if sort_btn.count() > 0:
            print("Clicking Sort button...")
            sort_btn.click()
            page.wait_for_timeout(2000)
            new_posts_item = page.locator('div[role="menuitem"], div[role="menuitemradio"]').filter(has_text='New posts').first
            if new_posts_item.count() > 0:
                print('Selecting "New posts"...')
                new_posts_item.click()
                page.wait_for_timeout(5000)

        # Scroll twice to load the very newest posts
        print("Scrolling slightly to load newest posts...")
        for _ in range(2):
            page.evaluate('window.scrollBy(0, 800)')
            page.wait_for_timeout(1500)

        # Identify target post containers currently in the DOM
        post_count = page.evaluate('''() => {
            const feed = document.querySelector('div[role="feed"]');
            if (!feed) return 0;
            const containers = feed.querySelectorAll('div.x1n2onr6.xh8yej3.x1ja2u2z.xod5an3');
            
            let count = 0;
            containers.forEach((c) => {
                const messageEl = c.querySelector('div[data-ad-comet-preview="message"]');
                if (messageEl) {
                    c.setAttribute('data-target-post', 'true');
                    count++;
                }
            });
            return count;
        }''')
        
        print(f"Found {post_count} posts containing message content.")
        
        posts = []
        feed_locator = page.locator('div[role="feed"]').first
        
        # Parse up to the first 3 posts
        for idx in range(min(post_count, 3)):
            post_locator = feed_locator.locator('div[data-target-post="true"]').nth(idx)
            
            # Author
            author = page.evaluate('''(postIdx) => {
                const post = document.querySelectorAll('div[data-target-post="true"]')[postIdx];
                const firstTextLink = Array.from(post.querySelectorAll('a')).find(a => a.innerText && a.innerText.trim().length > 0);
                return firstTextLink ? firstTextLink.innerText.trim() : 'Unknown Author';
            }''', idx)
            
            # Content
            content = page.evaluate('''(postIdx) => {
                const post = document.querySelectorAll('div[data-target-post="true"]')[postIdx];
                const msg = post.querySelector('div[data-ad-comet-preview="message"]');
                return msg ? msg.innerText.trim() : '';
            }''', idx)
            
            # Date via hover tooltip
            date_link_idx = page.evaluate('''(postIdx) => {
                const post = document.querySelectorAll('div[data-target-post="true"]')[postIdx];
                const links = Array.from(post.querySelectorAll('a'));
                return links.findIndex(a => a.getAttribute('href') && a.getAttribute('href').startsWith('?__cft__'));
            }''', idx)
            
            date_str = 'Unknown Date'
            if date_link_idx != -1:
                try:
                    date_link_loc = post_locator.locator('a').nth(date_link_idx)
                    date_link_loc.scroll_into_view_if_needed()
                    date_link_loc.hover()
                    page.wait_for_timeout(800)
                    date_str = page.evaluate('''() => {
                        const tooltip = document.querySelector('div[role="tooltip"]');
                        return tooltip ? tooltip.innerText.trim() : 'Unknown';
                    }''')
                except Exception as hover_err:
                    print(f"Hover failed for post {idx}: {hover_err}")
            
            if content:
                posts.append({
                    "author": author,
                    "date": date_str,
                    "content": content
                })

        # Take screenshot for debugging if no posts found
        if not posts:
            screenshot_path = "/home/will/pops/tmp/fb_group_error.png"
            page.screenshot(path=screenshot_path)
            print(f"Debug screenshot saved to {screenshot_path}")

        context.close()

    if not posts:
        print("No posts found. Facebook page layout might have changed or feed failed to load.")
        sys.exit(1)

    latest_post = posts[0]
    print(f"Latest post content preview: {latest_post['content'][:100]}...")
    print(f"Latest post author: {latest_post['author']}")
    print(f"Latest post date: {latest_post['date']}")

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
    
    is_new = False
    if isinstance(last_known_post, dict):
        if last_known_post.get("content") != latest_post["content"] or last_known_post.get("author") != latest_post["author"]:
            is_new = True
    else:
        is_new = True

    if is_new:
        print("New post detected!")
        # Save new state
        with open(STATE_FILE, 'w') as f:
            json.dump({"latest_post": latest_post, "updated_at": time.time()}, f)
        
        # Trigger notification
        msg_body = f"Author: {latest_post['author']}\nDate: {latest_post['date']}\n\n{latest_post['content']}"
        notify_via_hass(msg_body)
    else:
        print("No new posts detected.")

if __name__ == "__main__":
    main()
