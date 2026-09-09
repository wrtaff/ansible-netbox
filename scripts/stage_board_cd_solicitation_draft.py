#!/usr/bin/env python3
"""
================================================================================
Filename:       stage_board_cd_solicitation_draft.py
Version:        1.0
Author:         Gemini CLI / Antigravity
Last Modified:  2026-09-09
Context:        http://trac.gafla.us.com/ticket/4552
Related:        http://trac.gafla.us.com/ticket/2504

Purpose:
    Stages a Gmail draft to Rhonda Saltz (First Bank) soliciting current CD
    positions ahead of the monthly Mill 3 Board Meeting. Provides a human-in-the-
    loop approval gate where the email is placed into Gmail Drafts for review
    before sending.

Usage:
    # Stage draft for the upcoming meeting (auto-calculated 2nd Monday):
    python3 stage_board_cd_solicitation_draft.py

    # Dry-run inspection without creating draft:
    python3 stage_board_cd_solicitation_draft.py --dry-run

    # Specify explicit meeting date:
    python3 stage_board_cd_solicitation_draft.py --meeting-date 2026-10-12
================================================================================
"""

import argparse
import datetime
import os
import subprocess
import sys

TO_RECIPIENT = "Rhonda.Saltz@firstbankonline.com"
CC_RECIPIENTS = (
    "will@totalservicegroupllc.com,"
    "delaney@totalservicegroupllc.com,"
    "Michelle@totalservicegroupllc.com,"
    "toddrobertking@gmail.com,"
    "alaynegamache@gmail.com"
)
SUBJECT = "Re: First Bank CD statements"


def get_second_monday(year: int, month: int) -> datetime.date:
    """Calculates the date of the 2nd Monday for a given year and month."""
    first_day = datetime.date(year, month, 1)
    # weekday(): 0=Monday, 6=Sunday
    days_to_first_monday = (0 - first_day.weekday()) % 7
    first_monday = first_day + datetime.timedelta(days=days_to_first_monday)
    second_monday = first_monday + datetime.timedelta(weeks=1)
    return second_monday


def get_next_board_meeting(today: datetime.date = None) -> datetime.date:
    """Returns the date of the next upcoming 2nd Monday board meeting."""
    if today is None:
        today = datetime.date.today()

    this_month_meeting = get_second_monday(today.year, today.month)
    if today <= this_month_meeting:
        return this_month_meeting

    # Move to next month
    if today.month == 12:
        next_year = today.year + 1
        next_month = 1
    else:
        next_year = today.year
        next_month = today.month + 1

    return get_second_monday(next_year, next_month)


def main():
    parser = argparse.ArgumentParser(
        description="Stage a Gmail draft to Rhonda Saltz for CD statements ahead of board meeting."
    )
    parser.add_argument(
        "--meeting-date",
        help="Target meeting date (YYYY-MM-DD). Defaults to next 2nd Monday.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the email draft details without creating it in Gmail.",
    )

    args = parser.parse_args()

    if args.meeting_date:
        meeting_date = datetime.datetime.strptime(args.meeting_date, "%Y-%m-%d").date()
    else:
        meeting_date = get_next_board_meeting()

    meeting_display = meeting_date.strftime("%B %d, %Y")

    body = (
        f"Hi Ms Rhonda! Could I trouble you for our current CD positions ahead of our upcoming board meeting next week (on {meeting_display})?\n\n"
        "Hope this finds you well!\n\n"
        "Cheers,\n"
        "-will\n\n"
        "Will Taff\n"
        "Eagle & Phenix COA Board Secretary\n"
    )

    print(f"Target Meeting: {meeting_display} ({meeting_date.isoformat()})")
    print(f"To:      {TO_RECIPIENT}")
    print(f"CC:      {CC_RECIPIENTS}")
    print(f"Subject: {SUBJECT}")
    print("Body:")
    print("---")
    print(body.strip())
    print("---")

    if args.dry_run:
        print("[Dry Run] Draft not created.")
        return

    script_dir = os.path.dirname(os.path.abspath(__file__))
    mgr_path = os.path.join(script_dir, "google_workspace_manager.py")

    cmd = [
        sys.executable,
        mgr_path,
        "gmail-create-draft",
        "--cc",
        CC_RECIPIENTS,
        TO_RECIPIENT,
        SUBJECT,
        body,
    ]

    print("Creating Gmail draft via google_workspace_manager.py...")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Error creating draft: {res.stderr}")
        sys.exit(res.returncode)

    print("Success! Draft created in Gmail.")
    print(res.stdout.strip())
    print("\nNext Action: Review the draft in Gmail and hit Send when ready.")


if __name__ == "__main__":
    main()
