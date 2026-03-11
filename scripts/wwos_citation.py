#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/wwos_citation.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-03-10

Purpose:
    Utility for generating WWOS-style citations.
    Standard format: [URL TITLE] <ref>SOURCE: [URL TITLE] retrieved YYYY-MM-DD</ref>

Usage:
    ./wwos_citation.py <url> --title "Title" --source "Source"
================================================================================
"""
import sys
from datetime import datetime
import argparse

def format_wwos_citation(url, title=None, source=None, ref_only=False):
    """
    Formats a URL and title into a WWOS-style citation.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    display_title = title if title else url
    link_text = f"[{url} {display_title}]"
    source_prefix = f"{source}: " if source else ""
    
    ref_tag = f"<ref>{source_prefix}{link_text} retrieved {today}</ref>"
    
    if ref_only:
        return ref_tag
    return f"{link_text} {ref_tag}"

def main():
    parser = argparse.ArgumentParser(description="Generate a WWOS-style citation.")
    parser.add_argument("url", help="The URL to cite")
    parser.add_argument("-t", "--title", help="Title for the link")
    parser.add_argument("-s", "--source", help="Source name (e.g., 'Wikipedia', 'Google Drive')")
    parser.add_argument("-r", "--ref-only", action="store_true", help="Only return the <ref>...</ref> part")
    
    args = parser.parse_args()
    print(format_wwos_citation(args.url, args.title, args.source, args.ref_only))

if __name__ == "__main__":
    main()
