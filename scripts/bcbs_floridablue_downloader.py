#!/usr/bin/env python3
"""
Filename:       bcbs_floridablue_downloader.py
Version:        1.0
Author:         Antigravity (Jimmy persona)
Last Modified:  2026-07-24
Context:        Eldercare / Health Insurance (BCBS Florida Blue)

Purpose:
    Automated Playwright script to log in to the Florida Blue portal,
    navigate to "My Health Statements", download PDF EOBs since a specified
    date (default 2026-03-17), and upload them to a designated Google Drive folder.
    Supports session caching (storageState) and automated Gmail-based MFA retrieval.

Usage:
    /opt/venvs/gemini_projects/bin/python3 bcbs_floridablue_downloader.py [--headed] [--since YYYY-MM-DD]
"""

import os
import sys
import re
import time
import argparse
from datetime import datetime
import base64

# Add standard scripts path to load google_workspace_manager
SCRIPTS_DIR = "/home/will/ansible-netbox/scripts"
if SCRIPTS_DIR not in sys.path:
    sys.path.append(SCRIPTS_DIR)

try:
    from googleapiclient.discovery import build
    from google_workspace_manager import get_creds, drive_upload_file
except ImportError as e:
    print(f"Error importing Google Workspace modules: {e}", file=sys.stderr)
    sys.exit(1)

from playwright.sync_api import sync_playwright, TimeoutError

# Default configuration
DEFAULT_USER = "taffwr"
DEFAULT_PASS = "BdS0IJbb3GFTGw"
DEFAULT_FOLDER = "1uscpaKczsOhl_e2s4DuXm239-rPuWEM7" # Google Drive EOB folder
DEFAULT_OUT_DIR = "/home/will/pops/tmp"
STATE_FILE = "/home/will/pops/tmp/bcbs_state.json"
LIMIT_DATE = datetime(2026, 3, 17)

def fetch_mfa_code():
    """Retrieve the latest 6-digit MFA code from Gmail."""
    print("Searching Gmail for the Florida Blue verification code...")
    creds = get_creds()
    service = build('gmail', 'v1', credentials=creds)
    
    # Wait for the email to arrive (poll up to 3 times, sleeping 10s between checks)
    for attempt in range(1, 4):
        print(f"Checking Gmail (attempt {attempt}/3)...")
        try:
            results = service.users().messages().list(
                userId='me',
                q='from:notification@floridablue.com "verification code"',
                maxResults=3
            ).execute()
            messages = results.get('messages', [])
            
            for msg_meta in messages:
                msg = service.users().messages().get(
                    userId='me',
                    id=msg_meta['id'],
                    format='minimal'
                ).execute()
                
                # Verify that the email is recent (internalDate within the last 3 minutes)
                internal_date_ms = int(msg.get('internalDate', 0))
                now_ms = time.time() * 1000
                if now_ms - internal_date_ms > 180000: # Older than 3 mins, skip
                    continue
                
                snippet = msg.get('snippet', '')
                match = re.search(r'verification code is:\s*(\d{6})', snippet, re.IGNORECASE)
                if match:
                    code = match.group(1)
                    print(f"Found MFA code: {code}")
                    return code
        except Exception as e:
            print(f"Gmail API check failed: {e}", file=sys.stderr)
            
        time.sleep(10)
        
    print("Failed to find a recent verification code in Gmail.", file=sys.stderr)
    return None

def login_flow(page, user, password, headed):
    """Handle full credential entry, user agreement, and MFA verification."""
    print("Navigating to login page...")
    page.goto("https://gwprofile.bcbsfl.com/profile/interstitial?locale=en")
    
    # Check if we are on the login form
    try:
        page.wait_for_selector("#NameCallback", timeout=15000)
    except TimeoutError:
        print("Login form not found. Current URL:", page.url)
        if not headed:
            page.screenshot(path=f"{DEFAULT_OUT_DIR}/login_error.png")
            print(f"Screenshot saved to {DEFAULT_OUT_DIR}/login_error.png")
        return False

    print("Filling credentials...")
    page.locator("#NameCallback").fill(user)
    page.locator("#PasswordCallback").fill(password)
    
    # Handle user agreement modal if present
    if page.locator("#legal-agree-btn").is_visible():
        print("Accepting legal agreement modal...")
        page.locator("#legal-agree-btn").click()
        page.wait_for_timeout(1000)
        # Refill if fields cleared
        page.locator("#NameCallback").fill(user)
        page.locator("#PasswordCallback").fill(password)
        
    print("Submitting login...")
    page.locator("#loginButton").click()
    page.wait_for_timeout(5000)

    # Check for MFA page
    if "Multi-Factor Authentication" in page.content() or page.locator("#nextButton").is_visible():
        print("MFA Challenge detected. Selecting email option...")
        # Continue with default selected (email)
        page.locator("#nextButton").click()
        page.wait_for_selector("#TextInputCallback", timeout=15000)
        
        # Retrieve code from Gmail and submit
        code = fetch_mfa_code()
        if not code:
            if not headed:
                page.screenshot(path=f"{DEFAULT_OUT_DIR}/mfa_error.png")
            raise Exception("Automated MFA retrieval failed. Run with --headed to enter manually.")
            
        page.locator("#TextInputCallback").fill(code)
        page.locator('button:has-text("Continue")').click()
        
    # Wait for dashboard navigation
    print("Waiting for dashboard to load...")
    try:
        page.wait_for_url("**/member/medicare/#/", timeout=30000)
        print("Successfully logged in.")
        return True
    except TimeoutError:
        print("Failed to reach dashboard. Current URL:", page.url)
        if not headed:
            page.screenshot(path=f"{DEFAULT_OUT_DIR}/dashboard_error.png")
        return False

def download_statements(page, limit_date, output_dir, drive_folder):
    """Navigate to statements list, download PDFs, and upload to Google Drive."""
    print("Navigating to Health Statements page...")
    page.goto("https://member.bcbsfl.com/member/medicare/#/healthstatements")
    page.wait_for_selector(".tab-title", timeout=20000)
    
    # Extract tab information
    tabs_data = page.evaluate("""() => {
        return Array.from(document.querySelectorAll("button.tab-title")).map(el => ({
            id: el.id,
            text: el.innerText.trim()
        }));
    }""")
    
    downloaded_count = 0
    
    for tab in tabs_data:
        date_str = tab['text']
        try:
            tab_date = datetime.strptime(date_str, "%m/%d/%Y")
        except ValueError:
            print(f"Skipping tab with invalid date format: '{date_str}'")
            continue
            
        if tab_date <= limit_date:
            print(f"Reached date limit ({limit_date.strftime('%Y-%m-%d')}) at statement date {date_str}. Stopping.")
            break
            
        filename = f"{tab_date.strftime('%Y-%m-%d')}_TAFF_SR_BCBS-FL_EOB.pdf"
        dest_path = os.path.join(output_dir, filename)
        
        print(f"Downloading statement for date {date_str}...")
        
        # Click the tab
        page.locator(f"#{tab['id'].replace('/', '\\\\/') if '/' in tab['id'] else tab['id']}").click()
        page.wait_for_timeout(2000)
        
        # Wait for the iframe blob to load/update
        try:
            page.wait_for_selector('iframe[src^="blob:"]', timeout=15000)
        except TimeoutError:
            print(f"Timeout waiting for PDF viewer iframe for statement {date_str}.")
            continue
            
        # Extract the blob as base64 in browser context
        base64_data = page.evaluate("""async () => {
            const iframe = document.querySelector('iframe[src^="blob:"]');
            if (!iframe) return null;
            const res = await fetch(iframe.src);
            const blob = await res.blob();
            return new Promise((resolve) => {
                const reader = new FileReader();
                reader.onloadend = () => resolve(reader.result.split(',')[1]);
                reader.readAsDataURL(blob);
            });
        }""")
        
        if not base64_data:
            print(f"Failed to extract PDF data for statement {date_str}.")
            continue
            
        # Save locally
        with open(dest_path, "wb") as f:
            f.write(base64.b64decode(base64_data))
        print(f"Saved locally: {dest_path}")
        
        # Upload to Google Drive
        try:
            print(f"Uploading {filename} to Google Drive...")
            result = drive_upload_file(file_path=dest_path, parent_id=drive_folder)
            print(f"Uploaded successfully. File ID: {result.get('id') if isinstance(result, dict) else 'Uploaded'}")
            downloaded_count += 1
        except Exception as e:
            print(f"Failed to upload {filename} to Google Drive: {e}", file=sys.stderr)
            
    print(f"Downloaded and uploaded {downloaded_count} statement(s) successfully.")

def main():
    parser = argparse.ArgumentParser(description="Automate Florida Blue EOB statements download.")
    parser.add_argument("--headed", action="store_true", help="Run browser in headed mode.")
    parser.add_argument("--since", default="2026-03-17", help="Download statements since this date (YYYY-MM-DD).")
    parser.add_argument("--user", default=DEFAULT_USER, help="Florida Blue username.")
    parser.add_argument("--pass", dest="password", default=DEFAULT_PASS, help="Florida Blue password.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Local output directory.")
    parser.add_argument("--folder", default=DEFAULT_FOLDER, help="Google Drive parent folder ID.")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    
    try:
        since_date = datetime.strptime(args.since, "%Y-%m-%d")
    except ValueError:
        print("Invalid date format. Use YYYY-MM-DD.", file=sys.stderr)
        sys.exit(1)

    print(f"Starting Florida Blue statement downloader. Headed={args.headed}, Since={args.since}")
    
    with sync_playwright() as p:
        # Check if saved state is available
        launch_args = {
            "executable_path": "/usr/bin/google-chrome"
        }
        if not args.headed:
            launch_args["headless"] = True
        else:
            launch_args["headless"] = False
            
        browser = p.chromium.launch(**launch_args)
        
        # Configure context
        context_args = {}
        if os.path.exists(STATE_FILE):
            print(f"Loading session from state: {STATE_FILE}")
            context_args["storage_state"] = STATE_FILE
            
        context = browser.new_context(**context_args)
        page = context.new_page()
        
        try:
            # Navigate to statements directly to test session validity
            print("Checking session validity...")
            page.goto("https://member.bcbsfl.com/member/medicare/#/healthstatements")
            
            # Wait 5 seconds for client-side routing/auth checks to settle
            page.wait_for_timeout(5000)
            
            # Check if redirected to login
            if "gwlogin" in page.url or "memberauth" in page.url or "saml2authnrequest" in page.url or page.locator("#NameCallback").is_visible():
                print("Session expired or invalid. Running login flow...")
                success = login_flow(page, args.user, args.password, args.headed)
                if not success:
                    print("Login failed. Exiting.", file=sys.stderr)
                    sys.exit(1)
                # Save session state
                context.storage_state(path=STATE_FILE)
                print(f"Saved fresh session state: {STATE_FILE}")
            else:
                print("Session is valid.")
                
            # Perform download and upload
            download_statements(page, since_date, args.out_dir, args.folder)
            
        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    main()
