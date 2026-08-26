#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/freshrss_add_feed.py
Version:        1.0
Author:         Gemini CLI / opencode
Last Modified:  2026-08-25
Context:        http://trac.gafla.us.com/ticket/4398

Purpose:
    Automate adding a feed subscription to FreshRSS.
    Supports:
    1. Direct FreshRSS Google Reader API (when FRESHRSS_USER & FRESHRSS_PASSWORD set)
    2. Playwright Browser Automation (local browser or remote CDP connection)
    3. Web UI form submission fallback

Usage:
    # Google Reader API method:
    FRESHRSS_USER=will FRESHRSS_PASSWORD=secret python3 freshrss_add_feed.py \\
        --feed-url "http://ktn-lxc-01.home.arpa:8088/feeds/49tyujhfa96kbu2802d7.xml" \\
        --title "Columbus Ledger-Enquirer"

    # Playwright browser automation method (e.g. over CDP):
    python3 freshrss_add_feed.py \\
        --feed-url "http://ktn-lxc-01.home.arpa:8088/feeds/49tyujhfa96kbu2802d7.xml" \\
        --use-playwright --cdp-url "http://127.0.0.1:9222"
================================================================================
"""

import argparse
import asyncio
import os
import sys
import urllib.parse
import requests


DEFAULT_FRESHRSS_BASE_URL = "https://ynh2.van-bee.ts.net/freshrss"


def add_feed_via_greader_api(base_url, username, password, feed_url, title=None, category=None):
    """Subscribe to a feed via FreshRSS Google Reader API."""
    login_url = f"{base_url.rstrip('/')}/api/greader.php/accounts/ClientLogin"
    api_url = f"{base_url.rstrip('/')}/api/greader.php/reader/api/0"

    print(f"[*] Authenticating with FreshRSS Google Reader API ({login_url})...")
    resp = requests.post(login_url, data={"Email": username, "Passwd": password}, timeout=15)
    resp.raise_for_status()

    auth_token = None
    for line in resp.text.split("\n"):
        if line.startswith("Auth="):
            auth_token = line.split("=", 1)[1].strip()
            break

    if not auth_token:
        raise RuntimeError("Failed to extract Auth token from FreshRSS login response")

    headers = {"Authorization": f"GoogleLogin auth={auth_token}"}

    # Obtain action token
    token_resp = requests.get(f"{api_url}/token", headers=headers, timeout=15)
    token_resp.raise_for_status()
    action_token = token_resp.text.strip()

    print(f"[*] Subscribing to feed: {feed_url}...")
    sub_data = {
        "ac": "subscribe",
        "s": f"feed/{feed_url}",
        "T": action_token,
    }
    if title:
        sub_data["t"] = title
    if category:
        sub_data["a"] = f"user/-/label/{category}"

    edit_resp = requests.post(f"{api_url}/subscription/edit", headers=headers, data=sub_data, timeout=15)
    edit_resp.raise_for_status()
    print("[+] Successfully subscribed to feed via Google Reader API.")
    return True


async def add_feed_via_playwright(base_url, feed_url, title=None, category=None, cdp_url=None, headless=True):
    """Subscribe to a feed via FreshRSS Web UI using Playwright."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("[!] Playwright is not installed in the current Python environment.", file=sys.stderr)
        return False

    add_feed_url = f"{base_url.rstrip('/')}/i/?c=feed&a=add"
    print(f"[*] Navigating to FreshRSS add feed page ({add_feed_url})...")

    async with async_playwright() as p:
        if cdp_url:
            print(f"[*] Connecting to browser over CDP: {cdp_url}...")
            browser = await p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
        else:
            print(f"[*] Launching browser (headless={headless})...")
            browser = await p.chromium.launch(headless=headless)
            page = await browser.new_page()

        try:
            await page.goto(add_feed_url, timeout=20000)
            
            # Check if login is required
            if "login" in page.url.lower() or await page.locator("input[name='username']").count() > 0:
                print("[!] FreshRSS requires authentication. Log in or supply an authenticated session/CDP profile.")
                return False

            # Fill feed URL
            url_input = page.locator("input#url, input[name='url_rss']")
            await url_input.fill(feed_url)

            # Submit
            submit_btn = page.locator("button[type='submit'], input[type='submit']")
            await submit_btn.click()
            await page.wait_for_load_state("networkidle", timeout=15000)
            print("[+] Feed form submitted in FreshRSS.")
            return True
        finally:
            if not cdp_url:
                await browser.close()


def main():
    parser = argparse.ArgumentParser(description="Add a feed subscription to FreshRSS.")
    parser.add_argument("--feed-url", required=True, help="URL of the Atom/RSS feed to subscribe")
    parser.add_argument("--title", help="Optional title for the feed")
    parser.add_argument("--category", help="Optional category name in FreshRSS")
    parser.add_argument("--base-url", default=DEFAULT_FRESHRSS_BASE_URL, help="FreshRSS base URL")
    parser.add_argument("--use-playwright", action="store_true", help="Use Playwright automation instead of API")
    parser.add_argument("--cdp-url", help="CDP endpoint (e.g. http://127.0.0.1:9222) for Playwright")
    parser.add_argument("--headless", action="store_true", default=True, help="Run Playwright headlessly")
    args = parser.parse_args()

    user = os.getenv("FRESHRSS_USER")
    passwd = os.getenv("FRESHRSS_PASSWORD")

    if not args.use-playwright and user and passwd:
        try:
            add_feed_via_greader_api(args.base_url, user, passwd, args.feed_url, args.title, args.category)
            return
        except Exception as err:
            print(f"[!] API subscription failed: {err}. Trying fallback...")

    if args.use_playwright or args.cdp_url:
        success = asyncio.run(add_feed_via_playwright(
            args.base_url, args.feed_url, args.title, args.category, args.cdp_url, args.headless
        ))
        if success:
            return

    print("\n--- Manual Subscription Instructions ---")
    print(f"Open FreshRSS at: {args.base_url.rstrip('/')}/i/?c=feed&a=add")
    print(f"Feed URL: {args.feed_url}")
    if args.title:
        print(f"Title: {args.title}")


if __name__ == "__main__":
    main()
