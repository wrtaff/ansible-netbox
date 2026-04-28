#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/wwos_citation.py
Version:        1.1
Author:         Gemini CLI
Last Modified:  2026-04-28

Purpose:
    Utility for generating WWOS-style citations.
    Standard format: <ref>SOURCE: [URL TITLE] retrieved YYYY-MM-DD</ref>

Revision History:
    v1.1 (2026-04-28): Citation is now ref-only — the inline link before <ref>
                       was a duplicate. Full citation lives inside <ref> tags only.
    v1.0 (2026-03-10): Initial implementation.

Usage:
    ./wwos_citation.py <url> --title "Title" --source "Source"
================================================================================
"""
import sys
from datetime import datetime
import argparse

def format_wwos_citation(url, title=None, source=None):
    """
    Formats a URL and title into a WWOS-style citation.
    Returns only the <ref>...</ref> tag — the full citation belongs inside the
    ref, not duplicated as an inline link before it.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    display_title = title if title else url
    link_text = f"[{url} {display_title}]"
    source_prefix = f"{source}: " if source else ""
    return f"<ref>{source_prefix}{link_text} retrieved {today}</ref>"

def main():
    parser = argparse.ArgumentParser(description="Generate a WWOS-style citation.")
    parser.add_argument("url", help="The URL to cite")
    parser.add_argument("-t", "--title", help="Title for the link")
    parser.add_argument("-s", "--source", help="Source name (e.g., 'Wikipedia', 'Google Drive')")

    args = parser.parse_args()
    print(format_wwos_citation(args.url, args.title, args.source))

if __name__ == "__main__":
    main()
