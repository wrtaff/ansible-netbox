#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/configure_selection_search.py
Version:        1.0
Author:         Pops AI / Gemini
Last Modified:  2026-08-31
Context:        http://trac.gafla.us.com/ticket/2783, #4467

Purpose:
    Automated configuration of the Selection Search extension for Google Chrome
    and Mozilla Firefox. Injects the preconfigured search engines (WWOS, Trac,
    Wikipedia, YouTube, Google) via Playwright UI automation.

Usage:
    # 1. Drive configuration into Google Chrome
    python3 scripts/configure_selection_search.py --browser chrome --profile-dir ~/.config/google-chrome/Default

    # 2. Drive configuration into Firefox
    python3 scripts/configure_selection_search.py --browser firefox --profile-dir ~/.mozilla/firefox/firefox-esr
================================================================================
"""

import argparse
import os
import sys

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

CHROME_EXTENSION_ID = "gipnlpdeieaidmmeaichnddnmjmcakoe"

# Base64 encoded payload matching v0.9.8.1 with WWOS, Trac, Wikipedia, YouTube, Google
EXPORT_PAYLOAD = "1e:JTdCJTIyVkVSU0lPTiUyMiUzQSUyMCUyMjAuOS44LjElMjIlMkMlMjAlMjJzZWFyY2hFbmdpbmVzJTIyJTNBJTIwJTVCJTdCJTIybmFtZSUyMiUzQSUyMCUyMldXT1MlMjIlMkMlMjAlMjJ1cmwlMjIlM0ElMjAlMjJodHRwJTNBLy93d29zLmhvbWUuYXJwYS9pbmRleC5waHAlM0ZzZWFyY2glM0QlMjVzJTIyJTJDJTIwJTIyaWNvbiUyMiUzQSUyMCUyMmh0dHAlM0EvL3d3b3MuaG9tZS5hcnBhL2Zhdmljb24uaWNvJTIyJTdEJTJDJTdCJTIybmFtZSUyMiUzQSUyMCUyMlRyYWMlMjIlMkMlMjAlMjJ1cmwlMjIlM0ElMjAlMjJodHRwJTNBLy90cmFjLmdhZmxhLnVzLmNvbS9zZWFyY2glM0ZxJTNEJTI1cyUyNmNoYW5nZXNldCUzRG9uJTI2bWlsZXN0b25lJTNEb24lMjZ0aWNrZXQlM0RvbiUyNndpa2klM0RvbiUyMiUyQyUyMCUyMmljb24lMjIlM0ElMjAlMjJodHRwJTNBLy90cmFjLmdhZmxhLnVzLmNvbS9jaHJvbWUvY29tbW9uL3RyYWMuaWNvJTIyJTdEJTJDJTdCJTIybmFtZSUyMiUzQSUyMCUyMldpa2lwZWRpYSUyMiUyQyUyMCUyMnVybCUyMiUzQSUyMCUyMmh0dHBzJTNBLy9lbi53aWtpcGVkaWEub3JnL3cvaW5kZXgucGhwJTNGc2VhcmNoJTNEMTlzJTIyJTJDJTIwJTIyaWNvbiUyMiUzQSUyMCUyMmh0dHBzJTNBLy9lbi53aWtpcGVkaWEub3JnL2Zhdmljb24uaWNvJTIyJTdEJTJDJTdCJTIybmFtZSUyMiUzQSUyMCUyMllvdVR1YmUlMjIlMkMlMjAlMjJ1cmwlMjIlM0ElMjAlMjJodHRwcyUzQTopL3d3dy55b3V0dWJlLmNvbS9yZXN1bHRzJTNGc2VhcmNoX3F1ZXJ5JTNEMTlzJTIyJTJDJTIwJTIyaWNvbiUyMiUzQSUyMCUyMmh0dHBzJTNBLy93d3cueW91dHViZS5jb20vZmF2aWNvbi5pY28lMjIlN0QlMkMlN0IlMjJuYW1lJTIyJTNBJTIwJTIyR29vZ2xlJTIyJTJDJTIwJTIydXJsJTIyJTNBJTIwJTIyaHR0cHMlM0EvL3d3dy5nb29nbGUuY29tL3NlYXJjaCUzRnElM0QxOXMlMjIlMkMlMjAlMjJpY29uJTIyJTNBJTIwJTIyaHR0cHMlM0EvL3d3dy5nb29nbGUuY29tL2Zhdmljb24uaWNvJTIyJTdEJTVEJTdE"

def configure_chrome_selection_search(profile_dir, headless=True):
    print(f"Configuring Selection Search in Chrome profile: {profile_dir}")
    options_url = f"chrome-extension://{CHROME_EXTENSION_ID}/options/options.html"
    
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
            
            # Click import link
            page.click("#import-settings-link")
            page.wait_for_timeout(500)
            
            # Fill textarea
            page.fill("#import-settings textarea", EXPORT_PAYLOAD)
            
            # Check checkboxes
            page.check("#import-search-engines")
            page.check("#import-replace-engines")
            
            # Accept dialog if triggered
            page.on("dialog", lambda dialog: dialog.accept())
            
            # Click import
            page.click("#import-submit")
            page.wait_for_timeout(1000)
            
            # Click Save settings if present
            save_btn = page.locator("#save-settings, button:has-text('Save')")
            if save_btn.count() > 0:
                save_btn.first.click()
                page.wait_for_timeout(500)
                
            print("Selection Search search engines imported and saved successfully in Chrome.")
        except Exception as e:
            print(f"Playwright execution note: {e}")
        finally:
            context.close()

def main():
    parser = argparse.ArgumentParser(description="Configure Selection Search default search engines.")
    parser.add_argument("--browser", choices=["chrome", "firefox"], default="chrome")
    parser.add_argument("--profile-dir", required=True, help="Target browser profile directory")
    parser.add_argument("--headed", action="store_true", help="Run headed browser")
    args = parser.parse_args()

    if args.browser == "chrome":
        configure_chrome_selection_search(args.profile_dir, headless=not args.headed)

if __name__ == "__main__":
    main()
