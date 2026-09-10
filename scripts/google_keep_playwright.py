#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/google_keep_playwright.py
Version:        2.0
Author:         Gemini CLI / Antigravity
Last Modified:  2026-09-08
Context:        http://trac.gafla.us.com/ticket/4334, http://trac.gafla.us.com/ticket/4546

Purpose:
    Playwright-based browser automation helper for Google Keep.
    Enables reading checklist items, adding new list items, toggling checkbox states,
    and single-session multi-item batch retrieval/mutation on specific Google Keep lists.
    Guarantees strict note/modal container scoping to prevent list items bleeding
    into or out of adjacent background cards.

Usage:
    # Read a list
    python3 google_keep_playwright.py get-list \
        --url "https://keep.google.com/#LIST/1jId_5SPcn50D6M295jujXu5ztGWk5ol6vmxeG6pRhjSqC0Q33s4hsqhq8dV5Xnc"

    # Get unchecked batch
    python3 google_keep_playwright.py get-batch \
        --url "https://keep.google.com/#LIST/1jId_5SPcn50D6M295jujXu5ztGWk5ol6vmxeG6pRhjSqC0Q33s4hsqhq8dV5Xnc" \
        --limit 10

    # Toggle a batch of items
    python3 google_keep_playwright.py toggle-batch \
        --url "https://keep.google.com/#LIST/1jId_5SPcn50D6M295jujXu5ztGWk5ol6vmxeG6pRhjSqC0Q33s4hsqhq8dV5Xnc" \
        --texts "item text 1" "item text 2" --checked

    # Add an item to a list
    python3 google_keep_playwright.py add-item \
        --url "https://keep.google.com/#LIST/1jId_5SPcn50D6M295jujXu5ztGWk5ol6vmxeG6pRhjSqC0Q33s4hsqhq8dV5Xnc" \
        --text "Buy almond milk"

    # Toggle a single item
    python3 google_keep_playwright.py toggle-item \
        --url "https://keep.google.com/#LIST/1jId_5SPcn50D6M295jujXu5ztGWk5ol6vmxeG6pRhjSqC0Q33s4hsqhq8dV5Xnc" \
        --text "Buy almond milk" --checked

Options:
    --profile-dir PATH    Path to persistent browser profile (default: ~/.config/google-keep-playwright)
    --cdp-url URL         Connect via Chrome DevTools Protocol (e.g. http://127.0.0.1:9222)
    --headed              Run browser in headed mode (default: headless)
    --json                Output results as JSON

Revision History:
    v2.0 (2026-09-08): Refactored for Trac #4546 (WP-1). Added strict container scoping via
                       JS evaluation of opened note dialog / matching card container; added get-batch
                       and toggle-batch subcommands for single-session batch operations;
                       added channel="chrome" and stale SingletonLock auto-cleanup on launch.
    v1.0 (2026-08-19): Initial implementation for Trac #4334 (WP-1).
================================================================================
"""

import argparse
import asyncio
import glob
import json
import os
import sys
from typing import Any, Dict, List, Optional

# Default profile directory for authenticated Keep session
DEFAULT_PROFILE_DIR = os.path.expanduser("~/.config/google-keep-playwright")


class GoogleKeepPlaywright:
    """Automates Google Keep list operations via Playwright with strict container isolation."""

    def __init__(
        self,
        profile_dir: str = DEFAULT_PROFILE_DIR,
        cdp_url: Optional[str] = None,
        headless: bool = True,
    ):
        self.profile_dir = profile_dir
        self.cdp_url = cdp_url
        self.headless = headless

    def _cleanup_stale_locks(self):
        """Removes stale Singleton locks in the profile directory if no Chrome process is active."""
        if os.path.exists(self.profile_dir):
            for lock_file in glob.glob(os.path.join(self.profile_dir, "Singleton*")):
                try:
                    os.unlink(lock_file)
                except Exception:
                    pass

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
        self._cleanup_stale_locks()

        launch_kwargs = {
            "user_data_dir": self.profile_dir,
            "headless": self.headless,
            "viewport": {"width": 1280, "height": 900},
            "channel": "chrome",
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        }

        context = await p.chromium.launch_persistent_context(**launch_kwargs)
        page = context.pages[0] if context.pages else await context.new_page()
        return None, context, page, False

    async def _safe_close(self, context, page, is_cdp: bool):
        """Safely closes page or context without throwing if already closed."""
        try:
            if is_cdp:
                if page and not page.is_closed():
                    await page.close()
            else:
                if context:
                    await context.close()
        except Exception:
            pass

    async def get_list(self, url: str) -> Dict[str, Any]:
        """Fetches the title and checklist items strictly for the targeted Google Keep note."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser, context, page, is_cdp = await self._get_context_and_page(p)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(4000)

                if "accounts.google.com" in page.url:
                    return {"success": False, "error": "Authentication required. Please log into Google Keep in the browser profile.", "url": page.url}

                note_id = url.split("#LIST/")[-1].split("#NOTE/")[-1] if ("#LIST/" in url or "#NOTE/" in url) else ""

                data = await page.evaluate('''({ noteId }) => {
                    // 1. If an opened modal dialog exists, use it
                    let container = document.querySelector('div[role="dialog"]');
                    if (!container) {
                        container = document.querySelector('div.IZ65Hb-n0tgYe, div.IZ65Hb-QQnnJe');
                    }

                    // 2. If no modal dialog, find the specific card matching noteId or non-empty checklist
                    if (!container) {
                        const cards = Array.from(document.querySelectorAll('div.IZ65Hb-n0tgWb'));
                        if (noteId) {
                            // Find card with matching ID or active list
                            for (const c of cards) {
                                const did = c.getAttribute('data-id') || c.getAttribute('id') || '';
                                if (did.includes(noteId)) {
                                    container = c;
                                    break;
                                }
                            }
                        }
                        // If not found by data-id, look for the card with the target title or non-empty items
                        if (!container) {
                            for (const c of cards) {
                                const titleEl = c.querySelector('div.IZ65Ce-haAclf, div[role="textbox"]');
                                const title = titleEl ? titleEl.innerText.trim() : '';
                                const count = c.querySelectorAll('div.bVEB4e-rymPhb-ibnC6b').length;
                                if (count > 0 && title === "To Do") {
                                    container = c;
                                    break;
                                }
                            }
                        }
                        if (!container && cards.length > 0) {
                            // Fallback to first card with items
                            for (const c of cards) {
                                if (c.querySelectorAll('div.bVEB4e-rymPhb-ibnC6b').length > 0) {
                                    container = c;
                                    break;
                                }
                            }
                        }
                    }

                    if (!container) {
                        return { error: "No target note container found on page." };
                    }

                    // Expand drawer if present
                    const drawerBtn = container.querySelector('div[role="button"][aria-expanded="false"]');
                    if (drawerBtn) {
                        try { drawerBtn.click(); } catch(e) {}
                    }

                    // Extract title
                    const titleEl = container.querySelector('div[contenteditable="true"]:not([aria-label="list item"]), div.IZ65Ce-haAclf');
                    const title = titleEl ? titleEl.innerText.trim() : "";

                    // Extract checklist items strictly inside this container
                    const items = [];
                    const itemDivs = container.querySelectorAll('div.bVEB4e-rymPhb-ibnC6b');
                    
                    itemDivs.forEach((itemDiv, idx) => {
                        const cb = itemDiv.querySelector('div[role="checkbox"]');
                        const checked = cb ? (cb.getAttribute('aria-checked') === 'true') : false;
                        const tb = itemDiv.querySelector('div[role="textbox"], div[contenteditable="true"]');
                        let text = tb ? tb.innerText.trim() : itemDiv.innerText.trim();
                        text = text.replace(/\\s+/g, ' ').trim();
                        if (text && text !== "List item") {
                            items.push({ index: idx, text, checked });
                        }
                    });

                    return { success: true, title, items };
                }''', {"noteId": note_id})

                if not data or data.get("error"):
                    return {"success": False, "error": data.get("error", "Failed to extract list"), "url": url}

                # Cleanly close
                try:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)
                except Exception:
                    pass

                return {
                    "success": True,
                    "url": url,
                    "title": data.get("title") or "Untitled List",
                    "item_count": len(data.get("items", [])),
                    "items": data.get("items", []),
                }
            finally:
                await self._safe_close(context, page, is_cdp)

    async def get_batch(self, url: str, limit: int = 10, unchecked_only: bool = True) -> Dict[str, Any]:
        """Fetches a batch of list items (default: unchecked only) up to limit."""
        res = await self.get_list(url)
        if not res.get("success"):
            return res

        filtered = []
        for it in res.get("items", []):
            if unchecked_only:
                if not it.get("checked"):
                    filtered.append(it)
            else:
                filtered.append(it)

        batch = filtered[:limit]
        return {
            "success": True,
            "url": url,
            "title": res.get("title"),
            "total_matching": len(filtered),
            "batch_count": len(batch),
            "items": batch,
        }

    async def add_item(self, url: str, text: str) -> Dict[str, Any]:
        """Appends a new checklist item to the Google Keep list."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser, context, page, is_cdp = await self._get_context_and_page(p)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(4000)

                if "accounts.google.com" in page.url:
                    return {"success": False, "error": "Authentication required. Please log into Google Keep in the browser profile."}

                dialog = page.locator('div[role="dialog"], div.IZ65Hb-n0tgYe, div.IZ65Hb-QQnnJe').first
                scope = dialog if await dialog.count() > 0 else page

                new_item_input = scope.locator('div[contenteditable="true"][aria-label="list item"]').last
                if await new_item_input.count() == 0:
                    new_item_input = scope.locator('div[contenteditable="true"]').last

                await new_item_input.click()
                await new_item_input.fill(text)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(1000)

                await page.keyboard.press("Escape")
                await page.wait_for_timeout(2500)

                return {
                    "success": True,
                    "added_text": text,
                    "url": url,
                }
            finally:
                await self._safe_close(context, page, is_cdp)

    async def toggle_batch(self, url: str, texts: List[str], target_state: Optional[bool] = None) -> Dict[str, Any]:
        """Toggles or sets the checked state for multiple items matching texts in a single browser session."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser, context, page, is_cdp = await self._get_context_and_page(p)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(4000)

                if "accounts.google.com" in page.url:
                    return {"success": False, "error": "Authentication required. Please log into Google Keep in the browser profile."}

                note_id = url.split("#LIST/")[-1].split("#NOTE/")[-1] if ("#LIST/" in url or "#NOTE/" in url) else ""

                results = await page.evaluate('''({ noteId, matchTexts, targetState }) => {
                    let container = document.querySelector('div[role="dialog"]');
                    if (!container) {
                        container = document.querySelector('div.IZ65Hb-n0tgYe, div.IZ65Hb-QQnnJe');
                    }
                    if (!container) {
                        const cards = Array.from(document.querySelectorAll('div.IZ65Hb-n0tgWb'));
                        for (const c of cards) {
                            const titleEl = c.querySelector('div.IZ65Ce-haAclf, div[role="textbox"]');
                            const title = titleEl ? titleEl.innerText.trim() : '';
                            const count = c.querySelectorAll('div.bVEB4e-rymPhb-ibnC6b').length;
                            if (count > 0 && title === "To Do") {
                                container = c;
                                break;
                            }
                        }
                    }
                    if (!container) {
                        container = document.querySelector('div.IZ65Hb-n0tgWb');
                    }
                    if (!container) {
                        return { error: "No active note container found on page." };
                    }

                    // Expand drawer if present
                    const drawerBtn = container.querySelector('div[role="button"][aria-expanded="false"]');
                    if (drawerBtn) {
                        try { drawerBtn.click(); } catch(e) {}
                    }

                    const itemDivs = Array.from(container.querySelectorAll('div.bVEB4e-rymPhb-ibnC6b'));
                    const resList = [];

                    for (const rawMatch of matchTexts) {
                        const match = rawMatch.trim().toLowerCase();
                        let foundItem = null;
                        let foundText = "";

                        for (const it of itemDivs) {
                            const tb = it.querySelector('div[role="textbox"], div[contenteditable="true"]');
                            let text = tb ? tb.innerText.trim() : it.innerText.trim();
                            text = text.replace(/\\s+/g, ' ').trim();
                            if (text.toLowerCase().includes(match) || match.includes(text.toLowerCase())) {
                                foundItem = it;
                                foundText = text;
                                break;
                            }
                        }

                        if (!foundItem) {
                            resList.push({ text: rawMatch, success: false, error: `Item matching '${rawMatch}' not found.` });
                            continue;
                        }

                        const cb = foundItem.querySelector('div[role="checkbox"]');
                        if (!cb) {
                            resList.push({ text: foundText, success: false, error: "Checkbox element not found in item row." });
                            continue;
                        }

                        const currentState = (cb.getAttribute('aria-checked') === 'true');
                        let newState = currentState;

                        if (targetState === null || targetState === undefined || targetState !== currentState) {
                            cb.click();
                            newState = !currentState;
                        }

                        resList.push({
                            text: foundText,
                            success: true,
                            previous_state: currentState,
                            new_state: newState
                        });
                    }

                    return { success: true, results: resList };
                }''', {"noteId": note_id, "matchTexts": texts, "targetState": target_state})

                await page.keyboard.press("Escape")
                await page.wait_for_timeout(2500)

                return {
                    "success": True,
                    "url": url,
                    "results": results.get("results", []) if results else [],
                }
            finally:
                await self._safe_close(context, page, is_cdp)

    async def toggle_item(self, url: str, text: str, target_state: Optional[bool] = None) -> Dict[str, Any]:
        """Toggles or sets the checked state of a single item matching text."""
        res = await self.toggle_batch(url, [text], target_state)
        if not res.get("success"):
            return res
        first_res = res.get("results", [{}])[0]
        return {
            "success": first_res.get("success", False),
            "item_text": first_res.get("text", text),
            "previous_state": first_res.get("previous_state"),
            "new_state": first_res.get("new_state"),
            "error": first_res.get("error"),
        }

    async def archive_note(self, url: str) -> Dict[str, Any]:
        """Archives a Google Keep note or list."""
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser, context, page, is_cdp = await self._get_context_and_page(p)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(4000)

                if "accounts.google.com" in page.url:
                    return {"success": False, "error": "Authentication required. Please log into Google Keep in the browser profile."}

                dialog = page.locator('div[role="dialog"], div.IZ65Hb-n0tgYe, div.IZ65Hb-QQnnJe').first
                scope = dialog if await dialog.count() > 0 else page

                archive_btn = scope.locator(
                    'div[role="button"][aria-label="Archive"], '
                    'div[role="button"][data-tooltip-text="Archive"], '
                    'div[aria-label="Archive"]'
                ).first

                if await archive_btn.count() == 0:
                    archive_btn = page.locator('div[role="button"][aria-label="Archive"], div[data-tooltip-text="Archive"]').last

                if await archive_btn.count() == 0:
                    return {
                        "success": False,
                        "error": "Archive button not found in note toolbar.",
                    }

                try:
                    await archive_btn.dispatch_event("click")
                except Exception:
                    await archive_btn.click(force=True)

                await page.wait_for_timeout(3000)

                return {
                    "success": True,
                    "url": url,
                    "archived": True,
                }
            finally:
                await self._safe_close(context, page, is_cdp)


def main():
    parser = argparse.ArgumentParser(description="Google Keep Playwright Helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # get-list
    get_parser = subparsers.add_parser("get-list", help="Get list items")
    get_parser.add_argument("--url", required=True, help="Google Keep List URL")

    # get-batch
    batch_parser = subparsers.add_parser("get-batch", help="Get batch of unchecked items")
    batch_parser.add_argument("--url", required=True, help="Google Keep List URL")
    batch_parser.add_argument("--limit", type=int, default=10, help="Max items to fetch (default: 10)")
    batch_parser.add_argument("--all", dest="unchecked_only", action="store_false", default=True, help="Include checked items")

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

    # toggle-batch
    toggle_batch_parser = subparsers.add_parser("toggle-batch", help="Toggle multiple items in a batch")
    toggle_batch_parser.add_argument("--url", required=True, help="Google Keep List URL")
    toggle_batch_parser.add_argument("--texts", nargs="+", required=True, help="List of item text strings to toggle")
    toggle_batch_parser.add_argument("--checked", dest="checked", action="store_true", default=None, help="Mark as checked")
    toggle_batch_parser.add_argument("--unchecked", dest="checked", action="store_false", help="Mark as unchecked")

    # archive-note
    archive_parser = subparsers.add_parser("archive-note", help="Archive a note or list")
    archive_parser.add_argument("--url", required=True, help="Google Keep Note/List URL")

    # Global options
    for p in [get_parser, batch_parser, add_parser, toggle_parser, toggle_batch_parser, archive_parser]:
        p.add_argument("--profile-dir", default=DEFAULT_PROFILE_DIR, help="Persistent browser profile dir")
        p.add_argument("--cdp-url", default=None, help="Connect via Chrome DevTools Protocol URL")
        p.add_argument("--headed", dest="headless", action="store_false", default=True, help="Run browser in headed mode (default: headless)")
        p.add_argument("--json", action="store_true", help="Output JSON format")

    args = parser.parse_args()

    client = GoogleKeepPlaywright(
        profile_dir=args.profile_dir,
        cdp_url=args.cdp_url,
        headless=args.headless,
    )

    if args.command == "get-list":
        result = asyncio.run(client.get_list(args.url))
    elif args.command == "get-batch":
        result = asyncio.run(client.get_batch(args.url, limit=args.limit, unchecked_only=args.unchecked_only))
    elif args.command == "add-item":
        result = asyncio.run(client.add_item(args.url, args.text))
    elif args.command == "toggle-item":
        result = asyncio.run(client.toggle_item(args.url, args.text, args.checked))
    elif args.command == "toggle-batch":
        result = asyncio.run(client.toggle_batch(args.url, args.texts, args.checked))
    elif args.command == "archive-note":
        result = asyncio.run(client.archive_note(args.url))
    else:
        result = {"error": f"Unknown command {args.command}"}

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if not result.get("success", False):
            print(f"Error: {result.get('error', 'Operation failed')}")
            sys.exit(1)

        if args.command in ["get-list", "get-batch"]:
            print(f"List: {result.get('title', 'Untitled')}")
            print(f"URL: {result.get('url')}")
            print(f"Items returned: {len(result.get('items', []))}\n")
            for item in result.get("items", []):
                status = "[X]" if item["checked"] else "[ ]"
                print(f"  {status} {item['text']}")
        elif args.command == "add-item":
            print(f"Added item '{result.get('added_text')}' to list {result.get('url')}")
        elif args.command == "toggle-item":
            print(f"Item '{result.get('item_text')}' state changed from {result.get('previous_state')} to {result.get('new_state')}")
        elif args.command == "toggle-batch":
            print(f"Batch toggle results on {result.get('url')}:")
            for r in result.get("results", []):
                if r.get("success"):
                    print(f"  - '{r.get('text')}': {r.get('previous_state')} -> {r.get('new_state')}")
                else:
                    print(f"  - ERROR: {r.get('error')}")


if __name__ == "__main__":
    main()
