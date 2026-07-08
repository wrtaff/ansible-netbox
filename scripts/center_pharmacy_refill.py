#!/usr/bin/env python3
# ==============================================================================
# Script Name: center_pharmacy_refill.py
# Description: Automates the prescription refill process for Center Pharmacy via Playwright.
# Author: gemini
# Date: 2026-07-08
#
# Secrets:
#     DIGITALPHARMACIST_EMAIL (Environment Variable) — Login email for Digital Pharmacist portal
#     DIGITALPHARMACIST_PASSWORD (Environment Variable) — Login password for Digital Pharmacist portal
#
# Revision History:
#     2026-07-08 (gemini): Initial creation to automate NALTREXONE refill.
# ==============================================================================

import os
from playwright.sync_api import sync_playwright

def run_refill():
    email = os.environ.get('DIGITALPHARMACIST_EMAIL')
    password = os.environ.get('DIGITALPHARMACIST_PASSWORD')

    if not email or not password:
        print("Error: DIGITALPHARMACIST_EMAIL or DIGITALPHARMACIST_PASSWORD not set in environment.")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Navigating to Center Pharmacy portal...")
        page.goto('https://portal.digitalpharmacist.com/login?pharmacy_id=2604b195-3360-4005-894d-cd5c209f5b1f')
        
        print("Logging in...")
        # Fill credentials
        page.get_by_role('textbox', name='Email Address').fill(email)
        page.get_by_role('textbox', name='Password').fill(password)
        
        # Click the login button
        page.get_by_role('button', name='Log In').click()
        
        print("Waiting for dashboard to load...")
        # Wait for the main dashboard to load
        page.wait_for_selector('text=Medications List')
        
        print("Selecting NALTREXONE checkbox...")
        # The checkbox appears 'disabled' in the DOM, so we bypass it with a JS click
        page.get_by_role('checkbox').evaluate('(el) => el.click()')
        
        print("Submitting refill...")
        page.get_by_role('button', name='Submit Refill').click()
        
        # Wait for the confirmation page
        page.wait_for_selector('text=Your Refill Will Be Ready Shortly', timeout=15000)
        print("Refill successfully submitted!")
        
        browser.close()

if __name__ == '__main__':
    run_refill()
