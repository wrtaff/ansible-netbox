#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/format_trac_wiki.py
Version:        1.1
Author:         Gemini CLI
Last Modified:  2026-04-02
Context:        http://trac.home.arpa/ticket/3265
WWOS:           http://192.168.0.99/mediawiki/index.php/Trac_Wiki_Formatter

Purpose:
    A CLI wrapper for the Trac formatting library.
    Allows for piping Markdown or raw text for MoinMoin conversion.

    Update 1.1:
    - Finalized initial release and verified functionality.
    Update 1.0:
    - Initial release.
================================================================================
"""
import sys
import argparse
from lib.trac_formatter import markdown_to_moinmoin, sanitize_content, format_code

def main():
    parser = argparse.ArgumentParser(description="Format text for Trac Wiki.")
    parser.add_argument("-m", "--markdown", action="store_true", help="Convert Markdown to MoinMoin syntax.")
    parser.add_argument("-s", "--sanitize", action="store_true", help="Redact secrets and sensitive info.")
    parser.add_argument("-c", "--code", action="store_true", help="Wrap input in a Trac code block.")
    parser.add_argument("-f", "--file", help="Path to a file to read (defaults to stdin).")

    args = parser.parse_args()

    # Read input
    if args.file:
        try:
            with open(args.file, 'r') as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        content = sys.stdin.read()

    # Apply transformations
    if args.markdown:
        content = markdown_to_moinmoin(content)
    
    if args.sanitize:
        content = sanitize_content(content)
        
    if args.code:
        content = format_code(content)

    # Output to stdout
    print(content)

if __name__ == "__main__":
    main()
