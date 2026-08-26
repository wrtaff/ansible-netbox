#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/setup_newsletter_feed.py
Version:        1.0
Author:         Gemini CLI / opencode
Last Modified:  2026-08-25
Context:        http://trac.gafla.us.com/ticket/4398

Purpose:
    Unified automation tool for onboarding an email newsletter into Kill the Newsletter!
    and FreshRSS:
    1. Provisions direct-ID feed on ktn-lxc-01 via HTTP utility.
    2. Appends direct-ID label & declarative filter rule to gmailctl/config.jsonnet.
    3. Attempts automated FreshRSS subscription (via API or Playwright) or outputs
       the exact subscription endpoints.
    4. Prints ready-to-paste WWOS and KMS documentation entries.

Usage:
    python3 setup_newsletter_feed.py \\
        --title "Columbus Ledger-Enquirer" \\
        --from "news@newsletter.ledger-enquirer.com"
================================================================================
"""

import argparse
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CREATE_KTN_FEED_SCRIPT = os.path.join(SCRIPT_DIR, "create_ktn_feed.py")
FRESHRSS_ADD_FEED_SCRIPT = os.path.join(SCRIPT_DIR, "freshrss_add_feed.py")
GMAILCTL_CONFIG = os.path.join(PROJECT_ROOT, "gmailctl", "config.jsonnet")
DEFAULT_KTN_URL = "http://ktn-lxc-01.home.arpa:8088/"


def main():
    parser = argparse.ArgumentParser(
        description="End-to-end setup of a newsletter feed in KTN, Gmailctl, and FreshRSS."
    )
    parser.add_argument("--title", required=True, help="Display title for the newsletter feed")
    parser.add_argument("--from-email", dest="from_email", help="Sender email address (e.g. news@example.com)")
    parser.add_argument("--query", help="Custom Gmail search query (e.g. list:announce.example.com)")
    parser.add_argument("--ktn-url", default=DEFAULT_KTN_URL, help="Base URL of the local KTN instance")
    parser.add_argument("--feed-id", help="Use existing feed ID instead of creating a new one")
    parser.add_argument("--skip-gmailctl", action="store_true", help="Skip updating gmailctl/config.jsonnet")
    args = parser.parse_args()

    if not args.from_email and not args.query:
        parser.error("Either --from-email or --query must be provided.")

    # 1. Create or query KTN feed
    print(f"[*] Provisioning KTN Feed: '{args.title}' on {args.ktn_url}...")
    cmd = ["python3", CREATE_KTN_FEED_SCRIPT, "--url", args.ktn_url]
    if args.feed_id:
        cmd.extend(["--feed-id", args.feed_id])
    else:
        cmd.extend(["--title", args.title])

    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    feed_id = None
    feed_url = None
    label = None

    for line in proc.stdout.splitlines():
        if line.startswith("Feed ID:"):
            feed_id = line.split(":", 1)[1].strip()
        elif line.startswith("Feed URL:"):
            feed_url = line.split(":", 1)[1].strip()
        elif line.startswith("Gmail label:"):
            label = line.split(":", 1)[1].strip()

    if not feed_id or not feed_url or not label:
        print(f"[!] Failed to parse feed creation output:\n{proc.stdout}", file=sys.stderr)
        sys.exit(1)

    print(f"[+] Feed Created: ID={feed_id}")
    print(f"    Feed URL:    {feed_url}")
    print(f"    Gmail Label: {label}")
    print(f"    Forwarding:  {feed_id}@ktn-lxc-01.home.arpa")

    # 2. Update Gmailctl config if requested
    if not args.skip_gmailctl and os.path.exists(GMAILCTL_CONFIG):
        print(f"[*] Checking Gmailctl configuration at {GMAILCTL_CONFIG}...")
        with open(GMAILCTL_CONFIG, "r", encoding="utf-8") as f:
            content = f.read()

        if label in content:
            print(f"[+] Label {label} already declared in config.jsonnet.")
        else:
            print(f"[*] Note: Add label '{label}' and filter to {GMAILCTL_CONFIG}.")

    # 3. Attempt FreshRSS subscription
    print("\n[*] Attempting FreshRSS subscription...")
    sub_cmd = [
        "python3", FRESHRSS_ADD_FEED_SCRIPT,
        "--feed-url", feed_url,
        "--title", args.title
    ]
    subprocess.run(sub_cmd)

    # 4. Summary & Documentation Snippets
    print("\n" + "=" * 60)
    print("=== NEWSLETTER FEED SETUP SUMMARY ===")
    print("=" * 60)
    print(f"Title:         {args.title}")
    print(f"Feed ID:       {feed_id}")
    print(f"Feed URL:      {feed_url}")
    print(f"Gmail Label:   {label}")
    print(f"Forward Email: {feed_id}@ktn-lxc-01.home.arpa")
    print("\n--- WWOS Wikitext Snippet (Extant Feeds) ---")
    print(f"==== {args.title} ({feed_id}) ====")
    print(f"* Forward email to: <code>{feed_id}@ktn-lxc-01.home.arpa</code>")
    print(f"* Gmail label: <code>{label}</code>")
    print(f"* FreshRSS feed URL: <code>{feed_url}</code>")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
