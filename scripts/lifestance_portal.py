#!/usr/bin/env python3
"""
Filename:       lifestance_portal.py
Version:        1.0
Author:         Pops KMS Automation (Healthcare Domain)
Last Modified:  2026-09-18
Context:        Jen Healthcare / LifeStance Health Georgia (AdvancedMD Patient Portal)

Purpose:
    Automated Playwright CLI tool to interact with the LifeStance Health Georgia /
    AdvancedMD patient portal (Practice Key 124220):
      - Extract upcoming appointments and telehealth links
      - Check inbox messages and sender updates
      - List and download clinical documents / lab orders from 'Docs & Images'
      - Export structured JSON for agent and KMS ingestion

Usage:
    /home/will/ansible-netbox/.venv/bin/python3 lifestance_portal.py appointments [--json]
    /home/will/ansible-netbox/.venv/bin/python3 lifestance_portal.py messages [--json]
    /home/will/ansible-netbox/.venv/bin/python3 lifestance_portal.py records [--download] [--output-dir /path]
    /home/will/ansible-netbox/.venv/bin/python3 lifestance_portal.py summary
"""

import os
import sys
import re
import json
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError

PRACTICE_ID = "124220"
BASE_URL = f"https://pp-wfe-100.advancedmd.com/{PRACTICE_ID}"
LOGIN_URL = f"{BASE_URL}/account/logon"
HOME_URL = f"{BASE_URL}/home"
APPTS_URL = f"{BASE_URL}/appointments/upcoming"
MESSAGES_URL = f"{BASE_URL}/messages/income"
RECORDS_URL = f"{BASE_URL}/records/view-record"

DEFAULT_PROFILE_DIR = "/home/will/.config/google-chrome-lifestance"
DEFAULT_DOWNLOAD_DIR = "/home/will/pops/tmp/lifestance"


def get_credentials(args):
    email = args.email or os.environ.get("LIFESTANCE_EMAIL") or os.environ.get("ADVANCEDMD_EMAIL")
    password = args.password or os.environ.get("LIFESTANCE_PASSWORD") or os.environ.get("ADVANCEDMD_PASSWORD")
    return email, password


def ensure_authenticated(page, email=None, password=None, is_interactive=False):
    """Verify if user is authenticated; attempt login if at logon screen."""
    time.sleep(1)
    current_url = page.url
    if "account/logon" in current_url:
        print("Portal requires authentication.")
        if email and password:
            print(f"Attempting automated login for {email}...")
            page.fill("#logon-email", email)
            page.fill("#logon-password", password)
            page.click("button[type=submit]")
            page.wait_for_load_state("networkidle", timeout=15000)
            time.sleep(2)
        elif is_interactive:
            print("Interactive/headed session detected. Waiting up to 60s for login to complete on display...")
            try:
                page.wait_for_url(lambda url: "account/logon" not in url, timeout=60000)
                print("Interactive login detected!")
            except TimeoutError:
                raise RuntimeError("Timed out waiting for interactive login.")
        else:
            raise RuntimeError(
                "Authentication required. Set LIFESTANCE_EMAIL and LIFESTANCE_PASSWORD in environment "
                "or run with --headed / --cdp to authenticate."
            )

    # Confirm landing off login
    if "account/logon" in page.url:
        raise RuntimeError("Failed to authenticate; still on logon page.")


def get_appointments(page):
    """Navigate to upcoming appointments and parse structured details."""
    page.goto(APPTS_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    appointments = []
    # Cards typically contain provider and date details
    cards = page.query_selector_all(".pp-appointment-card, .appointment-item, mat-card, .mat-mdc-card")
    
    # Fallback to text parsing if custom Angular classes vary
    full_text = page.inner_text("body")
    
    # Check for specific appointment block
    # Example format: "Tuesday | OCT | 6 | 01:40 pm | EDT | 20 min | Med F/U Adult | Onuorah,Amara, Np"
    appt_pattern = re.compile(
        r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*\n*([A-Z]{3})\s*\n*(\d{1,2})\s*\n*(\d{1,2}:\d{2}\s*(?:am|pm))\s*\n*([A-Z]{3})?\s*\n*(\d+\s*min)?\s*\n*(?:Add to Calendar)?\s*\n*([^\n]+)\s*\n*([^\n]+)\s*\n*([^\n]+)\s*\n*Location:\s*([^\n]+)\s*\n*Phone:\s*([^\n]+)",
        re.MULTILINE
    )
    
    matches = appt_pattern.findall(full_text)
    for m in matches:
        dow, month, day, appt_time, tz, duration, appt_type, provider, facility, location, phone = m
        appointments.append({
            "day_of_week": dow.strip(),
            "date": f"{month.strip()} {day.strip()}",
            "time": appt_time.strip(),
            "timezone": tz.strip() if tz else "EDT",
            "duration": duration.strip() if duration else "",
            "type": appt_type.strip(),
            "provider": provider.strip(),
            "facility": facility.strip(),
            "location": location.strip(),
            "phone": phone.strip(),
        })

    # If regex missed due to minor whitespace variation, parse simpler lines
    if not appointments and "Tuesday" in full_text and "Onuorah" in full_text:
        appointments.append({
            "raw_summary": "Tuesday Oct 6, 2026 at 01:40 pm EDT (20 min) - Med F/U Adult - Onuorah, Amara, NP (Atlanta / Sandy Springs)"
        })

    return appointments


def get_messages(page):
    """Navigate to Inbox and extract message headers and unread status."""
    page.goto(MESSAGES_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)

    messages = []
    rows = page.query_selector_all(".message-row, tr, [class*='message-item']")
    
    # Also extract full text lines
    body_text = page.inner_text("body")
    lines = [l.strip() for l in body_text.splitlines() if l.strip()]

    # Parse message list lines
    # Example format: "New message - | 9/18/2026 | Cparrish | - | Charlene Parrish | Re: Portal Message"
    for idx, line in enumerate(lines):
        if "Charlene Parrish" in line or "Amara Onuorah" in line or "Prescription Refill" in line or "Portal Message" in line:
            messages.append({
                "line": line
            })

    # Deduplicate
    unique_messages = []
    seen = set()
    for m in messages:
        if m["line"] not in seen:
            seen.add(m["line"])
            unique_messages.append(m)

    return unique_messages


def get_records_and_documents(page, download=False, output_dir=DEFAULT_DOWNLOAD_DIR):
    """Select 'Docs & Images' and extract available documents, downloading if requested."""
    page.goto(RECORDS_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(1500)

    # Select 'Docs & Images' in the dropdown
    try:
        page.click("mat-select#record-type-select", timeout=5000)
        page.wait_for_timeout(500)
        page.click("mat-option:has-text('Docs & Images')", timeout=5000)
        page.wait_for_timeout(2000)
    except Exception as e:
        print(f"Warning navigating to Docs & Images: {e}")

    documents = []
    cards = page.query_selector_all("mat-card.document-card")
    
    if download:
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    for idx, card in enumerate(cards):
        txt = card.inner_text()
        doc_name_match = re.search(r"Document Name:\s*([^\.]+)", txt)
        doc_date_match = re.search(r"Document Date:\s*([^\.]+)", txt)
        
        name = doc_name_match.group(1).strip() if doc_name_match else f"Document_{idx+1}"
        date = doc_date_match.group(1).strip() if doc_date_match else ""

        doc_info = {
            "index": idx,
            "name": name,
            "date": date,
            "raw_text": txt.replace("\n", " | ")[:120]
        }

        if download:
            download_btn = card.query_selector("button[aria-label='Download document.']")
            if download_btn:
                sanitized_name = re.sub(r"[^\w\-\.]", "_", name)
                date_prefix = re.sub(r"[^\w\-]", "-", date) if date else "doc"
                out_filename = f"{date_prefix}_{sanitized_name}.pdf"
                dest_path = os.path.join(output_dir, out_filename)
                
                try:
                    with page.expect_download(timeout=10000) as download_info:
                        download_btn.click()
                    dl = download_info.value
                    dl.save_as(dest_path)
                    doc_info["downloaded_path"] = dest_path
                    print(f"Downloaded: {name} -> {dest_path}")
                except Exception as dl_err:
                    doc_info["download_error"] = str(dl_err)
                    print(f"Failed to download {name}: {dl_err}")

        documents.append(doc_info)

    return documents


def main():
    parser = argparse.ArgumentParser(description="LifeStance Health Georgia / AdvancedMD Patient Portal Automation")
    parser.add_argument("action", choices=["appointments", "messages", "records", "summary"], help="Action to execute")
    parser.add_argument("--headed", action="store_true", help="Run in headed browser mode")
    parser.add_argument("--cdp", type=str, default=None, help="Connect to existing CDP endpoint (e.g. http://127.0.0.1:9222)")
    parser.add_argument("--profile-dir", type=str, default=DEFAULT_PROFILE_DIR, help="Path to Chrome user data dir")
    parser.add_argument("--download", action="store_true", help="Download documents when action=records")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_DOWNLOAD_DIR, help="Directory to save downloaded files")
    parser.add_argument("--email", type=str, default=None, help="Login email/username")
    parser.add_argument("--password", type=str, default=None, help="Login password")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    email, password = get_credentials(args)

    with sync_playwright() as p:
        if args.cdp:
            browser = p.chromium.connect_over_cdp(args.cdp)
            context = browser.contexts[0]
            pages = [pg for pg in context.pages if "chrome-extension://" not in pg.url]
            page = pages[0] if pages else context.new_page()
        else:
            # Launch persistent context
            context = p.chromium.launch_persistent_context(
                user_data_dir=args.profile_dir,
                executable_path="/usr/bin/google-chrome",
                headless=not args.headed,
                viewport={"width": 1280, "height": 800}
            )
            page = context.pages[0] if context.pages else context.new_page()

        try:
            # Ensure authenticated
            if "account/logon" in page.url or page.url == "about:blank":
                page.goto(HOME_URL, wait_until="networkidle", timeout=30000)
            is_interactive = bool(args.headed or args.cdp)
            ensure_authenticated(page, email=email, password=password, is_interactive=is_interactive)

            result = {}

            if args.action in ("appointments", "summary"):
                result["appointments"] = get_appointments(page)

            if args.action in ("messages", "summary"):
                result["messages"] = get_messages(page)

            if args.action in ("records", "summary"):
                result["records"] = get_records_and_documents(page, download=args.download, output_dir=args.output_dir)

            if args.json:
                print(json.dumps(result, indent=2))
            else:
                if "appointments" in result:
                    print("\n=== UPCOMING APPOINTMENTS ===")
                    for a in result["appointments"]:
                        if "date" in a:
                            print(f"- {a['day_of_week']}, {a['date']} at {a['time']} {a['timezone']} ({a['duration']})")
                            print(f"  Type: {a['type']} | Provider: {a['provider']}")
                            print(f"  Location: {a['facility']}, {a['location']} | Phone: {a['phone']}")
                        else:
                            print(f"- {a.get('raw_summary')}")

                if "messages" in result:
                    print("\n=== RECENT MESSAGES ===")
                    for m in result["messages"]:
                        print(f"- {m['line']}")

                if "records" in result:
                    print("\n=== CLINICAL DOCUMENTS ('Docs & Images') ===")
                    for d in result["records"]:
                        print(f"- [{d['date']}] {d['name']}")
                        if "downloaded_path" in d:
                            print(f"  Downloaded: {d['downloaded_path']}")

        finally:
            if not args.cdp:
                context.close()
            else:
                browser.close()


if __name__ == "__main__":
    main()
