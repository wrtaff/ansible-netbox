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

                # Wait for note dialog or card to load
                try:
                    await page.wait_for_selector('div[role="dialog"], div[data-id], div[aria-label="Title"], div[contenteditable="true"]', timeout=15000)
                except Exception:
                    pass

                # Locate the active dialog or note editor
                dialog = page.locator('div[role="dialog"]').first
                scope = dialog if await dialog.count() > 0 else page

                # Extract title
                title_locator = scope.locator('div[aria-label="Title"], div[contenteditable="true"]').first
                title = ""
                if await title_locator.count() > 0:
                    title = (await title_locator.text_content() or "").strip()

                # Extract list items
                # Google Keep checklist items have role="checkbox" or class markers
                items: List[Dict[str, Any]] = []

                # Find all checklist item rows
                row_locators = scope.locator('div[role="listitem"], div.gka-listitem, div[aria-label="List item"]')
                count = await row_locators.count()

                if count == 0:
                    # Fallback locator for list items
                    row_locators = scope.locator('div:has(> div[role="checkbox"])')
                    count = await row_locators.count()

                for i in range(count):
                    row = row_locators.nth(i)
                    checkbox = row.locator('div[role="checkbox"]').first
                    text_el = row.locator('div[contenteditable="true"], div[role="textbox"], span').first

                    checked = False
                    if await checkbox.count() > 0:
                        aria_checked = await checkbox.get_attribute("aria-checked")
                        checked = aria_checked == "true"

                    text = ""
                    if await text_el.count() > 0:
                        text = (await text_el.text_content() or "").strip()

                    if text:
                        items.append({
                            "index": i,
                            "text": text,
                            "checked": checked,
                        })

                return {
                    "success": True,
                    "url": url,
                    "title": title,
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

                # Locate active dialog or page
                dialog = page.locator('div[role="dialog"]').first
                scope = dialog if await dialog.count() > 0 else page

                # Find "List item" / "New list item" input
                new_item_input = scope.locator(
                    'div[aria-label="List item"][contenteditable="true"], '
                    'input[placeholder="List item"], '
                    'div[placeholder="List item"]'
                ).last

                if await new_item_input.count() == 0:
                    # Fallback to any contenteditable at the end of the list
                    new_item_input = scope.locator('div[contenteditable="true"]').last

                await new_item_input.click()
                await new_item_input.fill(text)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1500)

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

                dialog = page.locator('div[role="dialog"]').first
                scope = dialog if await dialog.count() > 0 else page

                # Find row containing the text
                row = scope.locator(f'div:has-text("{text}")').filter(has=page.locator('div[role="checkbox"]')).first

                if await row.count() == 0:
                    return {
                        "success": False,
                        "error": f"Item matching '{text}' not found in list.",
                    }

                checkbox = row.locator('div[role="checkbox"]').first
                aria_checked = await checkbox.get_attribute("aria-checked")
                current_state = (aria_checked == "true")

                if target_state is None or target_state != current_state:
                    await checkbox.click()
                    await page.wait_for_timeout(1000)
                    new_state = not current_state
                else:
                    new_state = current_state

                return {
                    "success": True,
                    "item_text": text,
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
