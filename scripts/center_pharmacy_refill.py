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
#     TRAC_USER (Environment Variable) — User for Trac XML-RPC (defaults to 'will')
#     TRAC_PASSWORD (Environment Variable) — Password for Trac XML-RPC
#
# Revision History:
#     2026-07-08 (gemini): Added Trac ticket update functionality.
#     2026-07-08 (gemini): Initial creation to automate NALTREXONE refill.
# ==============================================================================

import os
import xmlrpc.client
from playwright.sync_api import sync_playwright

def update_trac_ticket():
    ticket_id = 2763
    trac_user = os.environ.get('TRAC_USER', 'will')
    trac_pass = os.environ.get('TRAC_PASSWORD')
    
    if not trac_pass:
        print("Warning: TRAC_PASSWORD not set, skipping Trac ticket update.")
        return

    auth_part = trac_user + ":" + trac_pass
    server_url = "http://" + auth_part + "@trac.home.arpa/login/xmlrpc"
    server = xmlrpc.client.ServerProxy(server_url)
    
    comment = "'''Automated Note:''' Center Pharmacy refill was successfully submitted via automated script."
    
    try:
        # Update ticket with the comment
        server.ticket.update(ticket_id, comment, {}, False)
        print(f"Successfully added confirmation comment to Trac ticket #{ticket_id}")
    except Exception as e:
        print(f"Failed to update Trac ticket #{ticket_id}: {e}")

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
        
    # After successful refill, update the Trac ticket
    update_trac_ticket()

if __name__ == '__main__':
    run_refill()
