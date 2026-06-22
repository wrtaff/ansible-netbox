#!/usr/bin/env python3
"""
================================================================================
Filename:       check_fb_group.py
Version:        2.0
Author:         Antigravity
Last Modified:  2026-06-22
Context:        Facebook Group Updates (EPSC)

Purpose:
    Scrape the EPSC Facebook group using Playwright with the persistent
    profile to check for new posts and comments. If new items are detected,
    notify via Email using google_workspace_manager.py.

Secrets:
    None - delegates to google_workspace_manager.py

Revision History:
    v2.0 (2026-06-22) - Email notifications, comment support, hash-based state.
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
import hashlib
from playwright.sync_api import sync_playwright

# Configuration
GROUP_URL = "https://www.facebook.com/groups/473971729877417/"
STATE_FILE = "/home/will/pops/tmp/fb_group_state.json"
PROFILE_DIR = "/home/will/.cache/ms-playwright/mcp-chrome-for-testing-f96f1ec" # Default Playwright MCP chrome profile
CHROME_PATH = "/usr/bin/google-chrome"
EMAIL_TO = "will@gafla.us.com"

def notify_via_email(subject, message):
    """Call Google Workspace Manager to send an email notification."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gws_manager = os.path.join(script_dir, "google_workspace_manager.py")
    
    try:
        subprocess.run(
            [sys.executable, gws_manager, "gmail-send", EMAIL_TO, subject, message],
            check=True,
            capture_output=True,
            text=True
        )
        print("Notification sent via Email.")
    except Exception as e:
        print(f"Failed to send email notification: {e}", file=sys.stderr)
        if hasattr(e, 'stderr') and e.stderr:
            print(e.stderr, file=sys.stderr)

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
            notify_via_email("EPSC Facebook Scraper: Session Expired", "Facebook session has expired. Please log back in using the Facebook Messenger skill to refresh the session.")
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

        # Expand comments if possible
        print("Expanding comments...")
        comment_buttons = page.locator('div[role="button"]').filter(has_text=' comments')
        for i in range(min(comment_buttons.count(), 3)):
            try:
                comment_buttons.nth(i).click()
                page.wait_for_timeout(1000)
            except:
                pass
        
        # Scroll slightly to load newest posts
        print("Scrolling slightly to load newest posts/comments...")
        for _ in range(3):
            page.evaluate('window.scrollBy(0, 800)')
            page.wait_for_timeout(1500)

        # Identify target post and comment containers currently in the DOM
        item_count = page.evaluate('''() => {
            const feed = document.querySelector('div[role="feed"]');
            if (!feed) return 0;
            
            let count = 0;
            
            // 1. Posts
            const postMessages = feed.querySelectorAll('div[data-ad-comet-preview="message"]');
            postMessages.forEach((msg) => {
                if (!msg.hasAttribute('data-target-item')) {
                    msg.setAttribute('data-target-item', 'post');
                    count++;
                }
            });
            
            // 2. Comments
            // Comments are typically in div[role="article"] which have aria-label starting with "Comment"
            const articles = feed.querySelectorAll('div[role="article"]');
            articles.forEach((article) => {
                const label = article.getAttribute('aria-label');
                if (label && label.startsWith("Comment")) {
                    const textDiv = article.querySelector('div[dir="auto"]');
                    if (textDiv && !textDiv.hasAttribute('data-target-item')) {
                        textDiv.setAttribute('data-target-item', 'comment');
                        let author = label.replace("Comment by ", "").replace("Comment from ", "");
                        textDiv.setAttribute('data-author', author);
                        count++;
                    }
                }
            });
            
            return count;
        }''')
        
        print(f"Found {item_count} items (posts and comments).")
        
        posts = []
        if item_count > 0:
            for idx in range(min(item_count, 15)): # Parse up to 15 items to ensure we catch everything
                try:
                    item_type = page.evaluate(f'''() => document.querySelectorAll('[data-target-item]')[{idx}].getAttribute('data-target-item')''')
                    
                    if item_type == 'post':
                        author = page.evaluate(f'''() => {{
                            const el = document.querySelectorAll('[data-target-item]')[{idx}];
                            const article = el.closest('div[role="article"]');
                            if (!article) return "Unknown Author";
                            const firstTextLink = Array.from(article.querySelectorAll('a')).find(a => a.innerText && a.innerText.trim().length > 0);
                            return firstTextLink ? firstTextLink.innerText.trim() : 'Unknown Author';
                        }}''')
                        content = page.evaluate(f'''() => document.querySelectorAll('[data-target-item]')[{idx}].innerText.trim()''')
                        is_comment = False
                    else:
                        author = page.evaluate(f'''() => document.querySelectorAll('[data-target-item]')[{idx}].getAttribute('data-author') || "Unknown Author"''')
                        content = page.evaluate(f'''() => document.querySelectorAll('[data-target-item]')[{idx}].innerText.trim()''')
                        is_comment = True

                    if content:
                        posts.append({
                            "author": author,
                            "content": content,
                            "is_comment": is_comment
                        })
                except Exception as e:
                    print(f"Error parsing item {idx}: {e}")

        # Take screenshot for debugging if no posts found
        if not posts:
            screenshot_path = "/home/will/pops/tmp/fb_group_error.png"
            page.screenshot(path=screenshot_path)
            print(f"Debug screenshot saved to {screenshot_path}")

        context.close()

    if not posts:
        print("No items found. Facebook page layout might have changed or feed failed to load.")
        sys.exit(1)

    print(f"Successfully extracted {len(posts)} items.")

    # Load old state
    old_state = {}
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                old_state = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load old state: {e}")

    notified_hashes = old_state.get("notified_hashes", [])
    
    # Migrate old state format if necessary
    if "latest_post" in old_state and isinstance(old_state["latest_post"], dict):
        old_content = old_state["latest_post"].get("content", "")
        old_author = old_state["latest_post"].get("author", "")
        old_hash = hashlib.md5((old_author + old_content).encode('utf-8')).hexdigest()
        if old_hash not in notified_hashes:
            notified_hashes.append(old_hash)

    new_items_found = False
    
    # Process from oldest to newest if we want to notify in order, but we grabbed them top-down (newest first).
    # Reversing the list so we process older items first if they are on the page.
    for post in reversed(posts):
        post_hash = hashlib.md5((post["author"] + post["content"]).encode('utf-8')).hexdigest()
        if post_hash not in notified_hashes:
            print(f"New {'comment' if post['is_comment'] else 'post'} detected by {post['author']}!")
            subject = f"EPSC FB {'Comment' if post['is_comment'] else 'Post'}: {post['author']}"
            msg_body = f"Author: {post['author']}\n\n{post['content']}"
            notify_via_email(subject, msg_body)
            
            notified_hashes.append(post_hash)
            new_items_found = True

    if new_items_found:
        # Keep only the last 200 hashes to prevent file growth
        notified_hashes = notified_hashes[-200:]
        with open(STATE_FILE, 'w') as f:
            json.dump({"notified_hashes": notified_hashes, "updated_at": time.time()}, f)
    else:
        print("No new posts/comments detected.")

if __name__ == "__main__":
    main()
