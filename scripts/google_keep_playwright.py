#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/google_keep_playwright.py
Version:        1.0
Author:         Gemini CLI / opencode
Last Modified:  2026-08-19
Context:        http://trac.gafla.us.com/ticket/4334

Purpose:
    Playwright-based browser automation helper for Google Keep.
    Enables reading checklist items, adding new list items, and toggling
    checkbox states on specific Google Keep list URLs.
    Designed to run on browser-capable hosts (such as limbo or athena)
    using persistent browser context profiles or CDP connection.

Usage:
    # Read a list
    python3 google_keep_playwright.py get-list \
        --url "https://keep.google.com/#LIST/1jId_5SPcn50D6M295jujXu5ztGWk5ol6vmxeG6pRhjSqC0Q33s4hsqhq8dV5Xnc"

    # Add an item to a list
    python3 google_keep_playwright.py add-item \
        --url "https://keep.google.com/#LIST/1jId_5SPcn50D6M295jujXu5ztGWk5ol6vmxeG6pRhjSqC0Q33s4hsqhq8dV5Xnc" \
        --text "Buy almond milk"

    # Toggle an item
    python3 google_keep_playwright.py toggle-item \
        --url "https://keep.google.com/#LIST/1jId_5SPcn50D6M295jujXu5ztGWk5ol6vmxeG6pRhjSqC0Q33s4hsqhq8dV5Xnc" \
        --text "Buy almond milk" --checked

Options:
    --profile-dir PATH    Path to persistent browser profile (default: ~/.config/google-keep-playwright)
    --cdp-url URL         Connect via Chrome DevTools Protocol (e.g. http://127.0.0.1:9222)
    --headless            Run in headless mode (default: false for login persistence / debugging)
    --json                Output results as JSON

Revision History:
    v1.0 (2026-08-19): Initial implementation for Trac #4334 (WP-1).
================================================================================
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Default profile directory for authenticated Keep session
DEFAULT_PROFILE_DIR = os.path.expanduser("~/.config/google-keep-playwright")


class GoogleKeepPlaywright:
    """Automates Google Keep list operations via Playwright."""

    def __init__(
        self,
        profile_dir: str = DEFAULT_PROFILE_DIR,
        cdp_url: Optional[str] = None,
        headless: bool = False,
    ):
        self.profile_dir = profile_dir
        self.cdp_url = cdp_url
        self.headless = headless

    async def _get_context_and_page(self, p):
        """Initializes browser context via CDP or persistent user data directory."""
        if self.cdp_url:
            browser = await p.chromium.connect_over_cdp(self.cdp_url)
            contexts = browser.contexts
            if contexts:
                context = contexts[0]
            else:
                context = await browser.new_context()
            page = await context.new_page()
            return browser, context, page, True

        os.makedirs(self.profile_dir, exist_ok=True)
        # Use system Google Chrome if available
        launch_kwargs = {
            "user_data_dir": self.profile_dir,
            "headless": self.headless,
            "viewport": {"width": 1280, "height": 900},
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        }
        if os.path.exists("/usr/bin/google-chrome"):
            launch_kwargs["channel"] = "chrome"

        context = await p.chromium.launch_persistent_context(**launch_kwargs)
        page = context.pages[0] if context.pages else await context.new_page()
        return None, context, page, False

    async def get_list(self, url: str) -> Dict[str, Any]:
        """Fetches the title and checklist items for a given Google Keep list URL."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser, context, page, is_cdp = await self._get_context_and_page(p)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                # Check if redirected to login
                if "accounts.google.com" in page.url:
                    return {
                        "success": False,
                        "error": "Authentication required. Please log into Google Keep in the browser profile.",
                        "url": page.url,
                    }

                # Find the active open note container via the list item editable
                item_editable = page.locator('div[contenteditable="true"][aria-label="list item"]').first
                if await item_editable.count() > 0:
                    scope = item_editable.locator('xpath=ancestor::div[contains(@class, "IZ65Hb")][last()]')
                else:
                    scope = page.locator('div.IZ65Hb-QQhtn, div.IZ65Hb-n0tgWb').first
                    if await scope.count() == 0:
                        scope = page

                # Extract title
                title_el = scope.locator('div[contenteditable="true"]:not([aria-label="list item"])').first
                title = ""
                if await title_el.count() > 0:
                    title = (await title_el.inner_text() or "").strip()

                # Extract list items within the opened note scope
                items: List[Dict[str, Any]] = []
                cbs = await scope.locator('div[role="checkbox"]').all()

                for i, cb in enumerate(cbs):
                    aria_checked = await cb.get_attribute("aria-checked")
                    checked = (aria_checked == "true")

                    # In Keep editor, the checklist item text is in the parent/grandparent or sibling editable
                    row = cb.locator("xpath=ancestor::div[contains(@class, 'haAclf') or count(../*) > 1][2]")
                    text = (await row.inner_text() or "").strip()

                    if not text:
                        # Fallback to parent text
                        parent = cb.locator("xpath=../..")
                        text = (await parent.inner_text() or "").strip()

                    if text and text != "List item":
                        items.append({
                            "index": i,
                            "text": text,
                            "checked": checked,
                        })

                return {
                    "success": True,
                    "url": url,
                    "title": title or "Untitled List",
                    "item_count": len(items),
                    "items": items,
                }
            finally:
                if not is_cdp:
                    await context.close()
                else:
                    await page.close()

    async def add_item(self, url: str, text: str) -> Dict[str, Any]:
        """Appends a new checklist item to the Google Keep list."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser, context, page, is_cdp = await self._get_context_and_page(p)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                if "accounts.google.com" in page.url:
                    return {
                        "success": False,
                        "error": "Authentication required. Please log into Google Keep in the browser profile.",
                    }

                dialog = page.locator('div.IZ65Hb-n0tgYe, div[role="dialog"], div.VIpgJd-TUoAZc').filter(
                    has=page.locator('div[contenteditable="true"][aria-label="list item"]')
                ).first
                scope = dialog if await dialog.count() > 0 else page

                # Find the "List item" input (contenteditable with aria-label="list item" or placeholder)
                new_item_input = scope.locator('div[contenteditable="true"][aria-label="list item"]').last
                if await new_item_input.count() == 0:
                    new_item_input = scope.locator('div[contenteditable="true"]').last

                await new_item_input.click()
                await new_item_input.fill(text)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2000)

                return {
                    "success": True,
                    "added_text": text,
                    "url": url,
                }
            finally:
                if not is_cdp:
                    await context.close()
                else:
                    await page.close()

    async def toggle_item(self, url: str, text: str, target_state: Optional[bool] = None) -> Dict[str, Any]:
        """Toggles or sets the checked state of an item matching text."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser, context, page, is_cdp = await self._get_context_and_page(p)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)

                if "accounts.google.com" in page.url:
                    return {
                        "success": False,
                        "error": "Authentication required. Please log into Google Keep in the browser profile.",
                    }

                dialog = page.locator('div.IZ65Hb-n0tgYe, div[role="dialog"], div.VIpgJd-TUoAZc').filter(
                    has=page.locator('div[contenteditable="true"][aria-label="list item"]')
                ).first
                scope = dialog if await dialog.count() > 0 else page

                checkboxes = await scope.locator('div[role="checkbox"]').all()
                target_cb = None
                target_txt = ""

                for cb in checkboxes:
                    parent = cb.locator("xpath=../..")
                    parent_txt = (await parent.inner_text() or "").strip()
                    if text.lower() in parent_txt.lower():
                        target_cb = cb
                        target_txt = parent_txt
                        break

                if not target_cb:
                    return {
                        "success": False,
                        "error": f"Item matching '{text}' not found in list.",
                    }

                aria_checked = await target_cb.get_attribute("aria-checked")
                current_state = (aria_checked == "true")

                if target_state is None or target_state != current_state:
                    await target_cb.click()
                    await page.wait_for_timeout(1500)
                    new_state = not current_state
                else:
                    new_state = current_state

                return {
                    "success": True,
                    "item_text": target_txt,
                    "previous_state": current_state,
                    "new_state": new_state,
                }
            finally:
                if not is_cdp:
                    await context.close()
                else:
                    await page.close()


def main():
    parser = argparse.ArgumentParser(description="Google Keep Playwright Helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # get-list
    get_parser = subparsers.add_parser("get-list", help="Get list items")
    get_parser.add_argument("--url", required=True, help="Google Keep List URL")

    # add-item
    add_parser = subparsers.add_parser("add-item", help="Add an item to list")
    add_parser.add_argument("--url", required=True, help="Google Keep List URL")
    add_parser.add_argument("--text", required=True, help="Text of item to add")

    # toggle-item
    toggle_parser = subparsers.add_parser("toggle-item", help="Toggle item checked state")
    toggle_parser.add_argument("--url", required=True, help="Google Keep List URL")
    toggle_parser.add_argument("--text", required=True, help="Text of item to toggle")
    toggle_parser.add_argument("--checked", dest="checked", action="store_true", default=None, help="Mark as checked")
    toggle_parser.add_argument("--unchecked", dest="checked", action="store_false", help="Mark as unchecked")

    # Global options
    for p in [get_parser, add_parser, toggle_parser]:
        p.add_argument("--profile-dir", default=DEFAULT_PROFILE_DIR, help="Persistent browser profile dir")
        p.add_argument("--cdp-url", default=None, help="Connect via Chrome DevTools Protocol URL")
        p.add_argument("--headless", action="store_true", help="Run browser in headless mode")
        p.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    client = GoogleKeepPlaywright(
        profile_dir=args.profile_dir,
        cdp_url=args.cdp_url,
        headless=args.headless,
    )

    if args.command == "get-list":
        result = asyncio.run(client.get_list(args.url))
    elif args.command == "add-item":
        result = asyncio.run(client.add_item(args.url, args.text))
    elif args.command == "toggle-item":
        result = asyncio.run(client.toggle_item(args.url, args.text, args.checked))
    else:
        result = {"error": f"Unknown command {args.command}"}

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if not result.get("success", False):
            print(f"Error: {result.get('error', 'Operation failed')}")
            sys.exit(1)

        if args.command == "get-list":
            print(f"List: {result.get('title', 'Untitled')}")
            print(f"URL: {result.get('url')}")
            print(f"Total Items: {result.get('item_count')}\n")
            for item in result.get("items", []):
                status = "[X]" if item["checked"] else "[ ]"
                print(f"  {status} {item['text']}")
        elif args.command == "add-item":
            print(f"Added item '{result.get('added_text')}' to list {result.get('url')}")
        elif args.command == "toggle-item":
            print(f"Item '{result.get('item_text')}' state changed from {result.get('previous_state')} to {result.get('new_state')}")


if __name__ == "__main__":
    main()
