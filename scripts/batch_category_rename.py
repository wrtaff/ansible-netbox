#!/usr/bin/env python3
"""
================================================================================
Filename:       batch_category_rename.py
Version:        1.2
Author:         Gemini
Last Modified:  2025-12-26

Purpose:
    Finds all pages in a given MediaWiki category and renames that category to
    a new one, leaving all other content and categories intact. This script is
    designed to be run for a one-off task and uses the functions from
    update_wwos_page.py for API interaction. This version includes more robust
    category matching, a dry-run mode, and a revert mode to fix previous errors.

Usage:
    # First, ensure your MediaWiki password is set as an environment variable:
    export WWOS_PASSWORD='your_password'

    # Dry-run: Show what changes would be made without saving
    ./batch_category_rename.py "Old Category" "New Category" --dry-run

    # Execute the category rename
    ./batch_category_rename.py "Old Category" "New Category"
    
    # Revert a botched edit by removing a spurious tag
    ./batch_category_rename.py --revert "[[Category:Spurious Tag]]"

Dependencies:
    - requests (pip install requests)
    - update_wwos_page.py (in the same directory)
================================================================================
"""
import sys
import argparse
import re
from update_wwos_page import get_wwos_page_content, update_wwos_page, SESSION, API_URL, _login

def get_pages_in_category(category_name):
    """
    Retrieves a list of pages belonging to a specific category.
    """
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{category_name}",
        "cmlimit": "500",  # Max limit
        "format": "json"
    }
    response = SESSION.get(API_URL, params=params)
    response.raise_for_status()
    data = response.json()
    return data.get("query", {}).get("categorymembers", [])

def main():
    parser = argparse.ArgumentParser(
        description="Rename a category for all pages that use it or revert a botched edit.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("old_category", nargs='?', default=None, help="The name of the category to rename (e.g., 'Christmas lighting')")
    parser.add_argument("new_category", nargs='?', default=None, help="The new name for the category (e.g., 'Christmas lights')")
    parser.add_argument("--dry-run", action="store_true", help="Show what changes would be made without saving.")
    parser.add_argument("--revert", metavar="SPURIOUS_TAG", help="Revert a botched edit by removing all instances of a given spurious tag.")
    
    args = parser.parse_args()

    try:
        # Establish a session by logging in
        _login()

        if args.revert:
            # Revert mode
            spurious_tag = args.revert
            print(f"--- REVERT MODE: Removing all instances of '{spurious_tag}' ---")
            
            # For this special case, we'll manually specify the pages we know were affected.
            affected_page_ids = [16026, 13507, 6843, 15971, 15972]
            
            for page_id in affected_page_ids:
                print(f"\n--- Processing page ID: {page_id} ---")
                current_content = get_wwos_page_content(page_id=page_id)
                
                if spurious_tag not in current_content:
                    print(f"Spurious tag not found in page ID {page_id}. Skipping.")
                    continue
                
                modified_content = current_content.replace(spurious_tag, "")
                
                if args.dry_run:
                    print(f"DRY RUN: Would remove '{spurious_tag}' from page ID {page_id}.")
                else:
                    summary = f"Automated revert: Removed spurious tag '{spurious_tag}'"
                    success = update_wwos_page(
                        page_id=page_id,
                        full_content=modified_content,
                        summary=summary
                    )
                    if not success:
                        print(f"Failed to revert page ID {page_id}. Halting.", file=sys.stderr)
                        sys.exit(1)
            print("\nRevert complete.")
            sys.exit(0)

        # Standard rename mode
        if not args.old_category or not args.new_category:
            parser.error("old_category and new_category are required for rename mode.")
        
        old_cat_name = args.old_category.strip()
        new_cat_name = args.new_category.strip()

        print(f"Attempting to rename category '{old_cat_name}' to '{new_cat_name}'...")
        if args.dry_run:
            print("DRY RUN: No changes will be saved.")

        pages = get_pages_in_category(old_cat_name)

        if not pages:
            print(f"No pages found in category '{old_cat_name}'. Exiting.")
            sys.exit(0)

        print(f"Found {len(pages)} pages to update.")

        for page in pages:
            page_id = page['pageid']
            page_title = page['title']
            print(f"\n--- Processing page: '{page_title}' (ID: {page_id}) ---")

            current_content = get_wwos_page_content(page_id=page_id)
            
            # Corrected and safer regex
            pattern = re.compile(
                r"\\\[\\\\[\s*Category\s*:\s*" + re.escape(old_cat_name) + r"\s*(\|.*?)?\s*\\\\]\\\\]",
                re.IGNORECASE
            )
            
            replacement_str = f"[[Category:{new_cat_name}]]"
            
            modified_content, num_replacements = pattern.subn(replacement_str, current_content)

            if num_replacements == 0:
                print(f"No changes needed for page '{page_title}'. The category tag was not found.")
                continue
            
            print(f"Found and would replace {num_replacements} instance(s) of the category tag.")

            if args.dry_run:
                print(f"DRY RUN: Page '{page_title}' would be updated.")
            else:
                summary = f"Automated edit: Renamed category '{old_cat_name}' to '{new_cat_name}'"
                success = update_wwos_page(
                    page_id=page_id,
                    full_content=modified_content,
                    summary=summary
                )
                if not success:
                    print(f"Failed to update page '{page_title}'. Halting.", file=sys.stderr)
                    sys.exit(1)
        
        print("\nAll pages processed successfully.")

    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
