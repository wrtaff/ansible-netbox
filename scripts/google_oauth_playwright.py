#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/google_oauth_playwright.py
Version:        1.0
Author:         Gemini CLI / opencode
Last Modified:  2026-08-19
Context:        http://trac.gafla.us.com/ticket/4334

Purpose:
    Automated OAuth 2.0 re-authentication for Google Workspace using Playwright.
    Drives the Google OAuth consent flow headlessly or via persistent browser
    context on browser-capable hosts (e.g. limbo, athena), eliminating manual
    browser approval prompts during token expiration.

Usage:
    # Run standalone automated re-auth
    python3 google_oauth_playwright.py [--port 8080] [--headless]

    # Run with specific browser profile
    python3 google_oauth_playwright.py --profile-dir ~/.config/google-oauth-playwright

    # Connect over CDP
    python3 google_oauth_playwright.py --cdp-url http://127.0.0.1:9222

Revision History:
    v1.0 (2026-08-19): Initial implementation for Trac #4334 (WP-2).
================================================================================
"""

import argparse
import asyncio
import os
import pickle
import sys
import threading
from typing import Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../"))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# Bootstrap venv if needed
def bootstrap():
    try:
        import google_auth_oauthlib
    except ImportError:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        venv_python = os.path.join(project_root, '.venv', 'bin', 'python3')
        if os.path.exists(venv_python) and sys.executable != venv_python:
            os.execv(venv_python, [venv_python] + sys.argv)

if __name__ == "__main__":
    bootstrap()

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Scopes and paths aligned with google_workspace_manager.py
from scripts.google_workspace_manager import SCOPES, CREDENTIALS_FILE, TOKEN_FILE

DEFAULT_PROFILE_DIR = os.path.expanduser("~/.config/google-keep-playwright")


async def complete_oauth_flow_in_browser(
    auth_url: str,
    profile_dir: str = DEFAULT_PROFILE_DIR,
    cdp_url: Optional[str] = None,
    headless: bool = True,
    account_email: Optional[str] = None,
) -> bool:
    """Uses Playwright to navigate the Google OAuth consent screen and approve access."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        if cdp_url:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            contexts = browser.contexts
            context = contexts[0] if contexts else await browser.new_context()
            page = await context.new_page()
            is_cdp = True
        else:
            os.makedirs(profile_dir, exist_ok=True)
            launch_kwargs = {
                "user_data_dir": profile_dir,
                "headless": headless,
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
            is_cdp = False

        try:
            print(f"[oauth-playwright] Navigating to OAuth authorization URL...")
            await page.goto(auth_url, wait_until="networkidle", timeout=30000)

            # Step 1: Account Chooser (if presented)
            if "Choose an account" in (await page.content()) or "accounts.google.com/AccountChooser" in page.url:
                print("[oauth-playwright] Account chooser detected.")
                if account_email:
                    account_btn = page.locator(f'div[data-email="{account_email}"], div:has-text("{account_email}")').first
                    if await account_btn.count() > 0:
                        await account_btn.click()
                        await page.wait_for_timeout(2000)
                else:
                    # Choose first available account
                    first_account = page.locator('li:has(div[data-email]), div[data-identifier]').first
                    if await first_account.count() > 0:
                        await first_account.click()
                        await page.wait_for_timeout(2000)

            # Step 2: Google unverified app warning ("Advanced" -> "Go to ... (unsafe)")
            unverified_hdr = page.locator('text="Google hasn’t verified this app", text="Google hasn\'t verified this app"')
            if await unverified_hdr.count() > 0:
                print("[oauth-playwright] Bypassing unverified app warning...")
                advanced_btn = page.locator('#advancedButton, button:has-text("Advanced"), a:has-text("Advanced")').first
                if await advanced_btn.count() > 0:
                    await advanced_btn.click()
                    await page.wait_for_timeout(1000)

                    unsafe_link = page.locator('a[id*="action-link"], a:has-text("Go to")').first
                    if await unsafe_link.count() > 0:
                        await unsafe_link.click()
                        await page.wait_for_timeout(2000)

            # Step 3: Select permissions checkboxes if requested
            select_all = page.locator('input[type="checkbox"][id="select-all"], text="Select all"').first
            if await select_all.count() > 0:
                print("[oauth-playwright] Selecting all permission checkboxes...")
                await select_all.click()
                await page.wait_for_timeout(500)

            # Step 4: Click Continue / Allow button
            continue_btn = page.locator(
                'button:has-text("Continue"), '
                'button:has-text("Allow"), '
                'div[role="button"]:has-text("Continue"), '
                'div[role="button"]:has-text("Allow"), '
                '#submit_approve_access'
            ).first

            if await continue_btn.count() > 0:
                print("[oauth-playwright] Approving OAuth permissions...")
                await continue_btn.click()
                await page.wait_for_timeout(3000)

            # Wait for redirect back to local callback URL (127.0.0.1)
            try:
                await page.wait_for_url(lambda u: "127.0.0.1" in u or "localhost" in u, timeout=15000)
                print(f"[oauth-playwright] Successfully redirected to callback: {page.url}")
                return True
            except Exception:
                # Check if page reached callback or success screen
                if "127.0.0.1" in page.url or "The authentication flow has completed" in await page.content():
                    return True
                print(f"[oauth-playwright] Warning: Callback redirect not confirmed. Current URL: {page.url}")
                return False

        finally:
            if not is_cdp:
                await context.close()
            else:
                await page.close()


def run_automated_reauth(
    port: int = 8080,
    profile_dir: str = DEFAULT_PROFILE_DIR,
    cdp_url: Optional[str] = None,
    headless: bool = True,
    account_email: Optional[str] = None,
) -> bool:
    """Orchestrates local server flow with headless browser consent approval."""
    if not os.path.exists(CREDENTIALS_FILE):
        raise FileNotFoundError(f"Google credentials file not found: {CREDENTIALS_FILE}")

    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    auth_url, _ = flow.authorization_url(
        prompt="consent",
        access_type="offline",
        redirect_uri=f"http://127.0.0.1:{port}/",
    )

    # Run the browser automation in an async task / thread while local server listens
    loop = asyncio.new_event_loop()

    def drive_browser():
        asyncio.set_event_loop(loop)
        # Small delay to ensure local server is listening
        loop.run_until_complete(asyncio.sleep(1.5))
        loop.run_until_complete(
            complete_oauth_flow_in_browser(
                auth_url=auth_url,
                profile_dir=profile_dir,
                cdp_url=cdp_url,
                headless=headless,
                account_email=account_email,
            )
        )

    browser_thread = threading.Thread(target=drive_browser, daemon=True)
    browser_thread.start()

    print(f"[oauth-playwright] Starting local authentication server on port {port}...")
    try:
        creds = flow.run_local_server(
            host="127.0.0.1",
            port=port,
            prompt="consent",
            open_browser=False,
        )

        with open(TOKEN_FILE, "wb") as token:
            pickle.dump(creds, token)

        print(f"[oauth-playwright] Authentication successful! Saved updated credentials to {TOKEN_FILE}")
        return True
    except Exception as e:
        print(f"[oauth-playwright] Authentication failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Automated Google OAuth 2.0 Re-authentication via Playwright")
    parser.add_argument("--port", type=int, default=8080, help="Local redirect server port (default: 8080)")
    parser.add_argument("--profile-dir", default=DEFAULT_PROFILE_DIR, help="Browser profile directory")
    parser.add_argument("--cdp-url", default=None, help="Connect via CDP URL")
    parser.add_argument("--headed", action="store_true", help="Run browser headed instead of headless")
    parser.add_argument("--account", default=None, help="Google account email to select in chooser")

    args = parser.parse_args()

    success = run_automated_reauth(
        port=args.port,
        profile_dir=args.profile_dir,
        cdp_url=args.cdp_url,
        headless=not args.headed,
        account_email=args.account,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
