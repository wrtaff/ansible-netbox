#!/usr/bin/env python3
"""
NFCU Member Transfer Playwright Runner
Automates member transfer after manual user login.
"""
import sys
import os
import time
import argparse
from playwright.sync_api import sync_playwright

def run_transfer(amount="149.03", to_acct="7143", from_acct="8705", display=":50.0"):
    os.environ["DISPLAY"] = display
    trigger_file = "/tmp/nfcu_continue_trigger"
    if os.path.exists(trigger_file):
        os.remove(trigger_file)
        
    print(f"[*] Starting headed browser session on DISPLAY={display}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            executable_path="/usr/bin/google-chrome",
            args=["--start-maximized"]
        )
        context = browser.new_context(viewport=None)
        page = context.new_page()
        
        print("[*] Navigating to NFCU homepage (https://www.navyfederal.org/)...")
        page.goto("https://www.navyfederal.org/")
        print("[!] Waiting for user to complete login and 2FA (or trigger file)...")
        
        # Wait until user reaches authenticated portal or trigger file is touched
        active_page = page
        while True:
            if os.path.exists(trigger_file):
                print(f"[+] Trigger file detected ({trigger_file})! Proceeding...")
                os.remove(trigger_file)
                # Find active page among all context pages
                for p_iter in context.pages:
                    if "navyfederal.org" in p_iter.url:
                        active_page = p_iter
                        break
                break
                
            for p_iter in context.pages:
                u = p_iter.url
                if "digitalomni.navyfederal.org" in u:
                    # If we see accounts, dashboard, or transfers, we are authenticated
                    if any(k in u for k in ["dashboard", "accounts", "move-money", "transfers", "overview"]):
                        print(f"[+] Login detected! Authenticated URL: {u}")
                        active_page = p_iter
                        break
            if active_page != page or ("digitalomni.navyfederal.org" in page.url and any(k in page.url for k in ["dashboard", "accounts", "move-money", "transfers"])):
                break
            time.sleep(2)
        
        # Give a moment for post-login scripts to settle
        time.sleep(2)
        
        transfer_url = "https://digitalomni.navyfederal.org/nfcu-online-banking/move-money/transfers/form"
        print(f"[*] Navigating to transfer form: {transfer_url}...")
        active_page.goto(transfer_url)
        active_page.wait_for_load_state("networkidle")
        time.sleep(3)
        
        # 1. Select TO Account First
        print(f"[*] Selecting destination account (*{to_acct})...")
        to_toggle = active_page.locator('[aria-label="Move Money To"], [data-id="move-money-to-product-selector_product-selector-toggle"]').first
        to_toggle.click()
        time.sleep(1)
        to_option = active_page.locator(f"text={to_acct}").first
        to_option.click()
        time.sleep(1)
        print(f"[+] Destination account selected.")
        
        # 2. Select FROM Account Second
        print(f"[*] Selecting source account (*{from_acct})...")
        from_toggle = active_page.locator('[aria-label="Move Money From"], [data-id="move-money-from-product-selector_product-selector-toggle"]').first
        from_toggle.click()
        time.sleep(1)
        from_option = active_page.locator(f"text={from_acct}").first
        from_option.click()
        time.sleep(1)
        print(f"[+] Source account selected.")
        
        # 3. Enter Amount
        print(f"[*] Entering transfer amount: ${amount}...")
        amt_input = active_page.locator('input[placeholder="0.00"], input[data-id="amount-input_currency-input"], [aria-label*="Amount"]').first
        amt_input.fill(str(amount))
        time.sleep(1)
        print(f"[+] Amount entered.")
        
        # 4. Click Continue to review page
        print("[*] Clicking Continue to reach review page...")
        continue_btn = active_page.locator('button:has-text("Continue"), [data-id="transfer-form-continue-button"]').first
        continue_btn.click()
        time.sleep(3)
        
        print(f"[+] Reached review screen! Current URL: {active_page.url}")
        print("[!] Ready for review and submission. Please confirm submission in browser.")
        
        # Keep browser open until user finishes or closes it
        try:
            while not active_page.is_closed():
                time.sleep(2)
        except Exception:
            pass
        print("[*] Browser session closed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NFCU Transfer Runner")
    parser.add_argument("--amount", default="149.03", help="Transfer amount")
    parser.add_argument("--to", default="7143", help="Destination account ending")
    parser.add_argument("--from-acct", default="8705", help="Source account ending")
    parser.add_argument("--display", default=":50.0", help="X11 Display")
    args = parser.parse_args()
    run_transfer(amount=args.amount, to_acct=args.to, from_acct=args.from_acct, display=args.display)
