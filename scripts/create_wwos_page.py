#!/usr/bin/env python3
"""
================================================================================
Filename:       create_wwos.py
Version:        2.3
Author:         Will
Last Modified:  2026-09-12

Purpose:
    Creates or updates pages on the WWOS MediaWiki instance. The script handles
    authentication, CSRF token management, and page content formatting
    automatically. Pages are created with a standard structure conforming to
    WWOS Manual of Style and wwos_page_check rules.

Usage:
    # First, set your MediaWiki password as an environment variable:
    export WWOS_PASSWORD='your_password'

    # Create a basic page with a single category:
    ./create_wwos.py "Page Name" "General"

    # Create a page with multiple categories (comma-separated):
    ./create_wwos.py "Page Name" "Application software, AI software, Agent-based software"

    # Create a page with inline content:
    ./create_wwos.py "Page Name" "Category" -c "Your page content here"

    # Create a page with content from a file:
    ./create_wwos.py "Page Name" "Category" -f /path/to/content.txt

    # Specify a custom edit summary:
    ./create_wwos.py "Page Name" "Category" -s "My custom edit summary"

    # Combine options with multiple categories:
    ./create_wwos.py "Page Name" "AI software, Tools" -f content.txt -s "New AI tool page"

Arguments:
    page_name           The title of the wiki page to create or update
    category            One or more categories, comma-separated 
                        (e.g., "General" or "AI software, Tools, Projects")
    -c, --content       Inline content string for the page body
    -f, --content-file  Path to a file containing the page content
    -s, --summary       Edit summary (default: "Page created by automated script")

MediaWiki Formatting Guide:
    - Newlines:       Standard newline characters (`\n`) in content files are 
                      correctly interpreted as new paragraphs. When passing
                      content via the `-c` flag, the shell may interpret
                      the newlines. Using a file (`-f`) is recommended for
                      complex, multi-line content.
    - Bold:           '''Your Text Here'''
    - Italics:        ''Your Text Here''
    - Links:          [[Page Name|Optional Link Text]] or [http://url.com Link Text]
    - Code Blocks:    <code>Your code here</code>

Version History:
    v2.3 (2026-09-12) - Fix Trac #4601:
        - Do not prepend bold title when content already has a valid opener.
        - Avoid duplicate {{bop}} / category blocks when already present in content.
        - Replace legacy {{baseOfPage}} with canonical {{bop}}.
        - Support list or string for categories, respect quotes, delimiters (;, |, \n), and prevent splitting category names containing commas (e.g. "Columbus, Georgia").
        - Omit {{bop}} and bold title for Category: pages.
    v2.2 (2025-12-12) - Added MediaWiki Formatting Guide to header.
    v2.1 (2025-12-11) - Multiple category support:
        - Enhanced category argument to accept comma-separated list of categories
          (e.g., "Application software, AI software, Agent-based software")
        - Script now adds a [[Category:X]] tag for each category specified
        - Categories are trimmed of leading/trailing whitespace
        - Updated help text and usage examples to reflect new functionality
        - Addresses limitation where only one category could be assigned per page

    v2.0 (2025-06-11) - Major rewrite and bug fixes:
        - Fixed syntax error: removed stray parenthesis from 'import argparse)'
        - Fixed truncated lines throughout the script
        - Restructured code: moved argparse logic out of create_wwos_page()
          function and into a proper main() function
        - Added if __name__ == "__main__" guard for proper script execution
        - Removed erroneous "createonly": False parameter (this param only
          accepts True or should be omitted entirely; omitting allows updates)
        - Added handling for "nochange" API response when content is identical
        - Actually call the create_wwos_page() function (was missing!)
        - Removed hardcoded password fallback for security; now requires
          WWOS_PASSWORD environment variable
        - Added proper return values (True/False) for success/failure
        - Implemented proper exit codes (0=success, 1=failure)
        - Changed error output to use sys.stderr
        - Used .get() for safer dictionary access throughout
        - Added IOError handling for file operations
        - Added usage examples to argparse help text

    v1.0 (Original) - Initial version with authentication and page creation

Dependencies:
    - requests (pip install requests)

Exit Codes:
    0 - Success (page created or updated)
    1 - Failure (authentication error, API error, or file not found)
================================================================================
"""
import argparse
import requests
import os
import sys
import re
import csv
from typing import Union, List, Optional

# MediaWiki API endpoint and credentials
API_URL = "http://wwos.home.arpa/api.php"
USERNAME = "will"
PASSWORD = os.getenv("WWOS_PASSWORD")

if not PASSWORD:
    # Try to find it in .bashrc
    bashrc_path = os.path.expanduser("~/.bashrc")
    if os.path.exists(bashrc_path):
        with open(bashrc_path, 'r') as f:
            for line in f:
                match = re.search(r'export WWOS_PASSWORD=[\'"]?([^\'"]+)[\'"]?', line)
                if match:
                    PASSWORD = match.group(1)
                    break


def get_authenticated_session():
    """
    Returns an authenticated requests.Session for the WWOS MediaWiki.
    """
    session = requests.Session()

    # 1. Get login token
    login_token_response = session.get(API_URL, params={
        "action": "query",
        "meta": "tokens",
        "type": "login",
        "format": "json"
    })
    login_token_response.raise_for_status()
    login_token = login_token_response.json()["query"]["tokens"]["logintoken"]

    # 2. Login to get session cookies
    login_response = session.post(API_URL, data={
        "action": "login",
        "lgname": USERNAME,
        "lgpassword": PASSWORD,
        "lgtoken": login_token,
        "format": "json"
    })
    login_response.raise_for_status()
    
    login_result = login_response.json()
    if login_result.get("login", {}).get("result") != "Success":
        raise Exception(f"Login failed: {login_result}")
        
    return session

def page_exists(page_name, session=None):
    """
    Checks if a page exists on the WWOS MediaWiki.
    """
    if session is None:
        session = get_authenticated_session()
        
    response = session.get(API_URL, params={
        "action": "query",
        "titles": page_name,
        "format": "json"
    })
    response.raise_for_status()
    data = response.json()
    
    pages = data.get("query", {}).get("pages", {})
    # If the page ID is "-1", it does not exist
    for page_id in pages:
        if page_id == "-1":
            return False
        return True
    return False

def get_page_content(page_name, session=None):
    """
    Retrieves the current content of a page.
    Returns None if page does not exist.
    """
    if session is None:
        session = get_authenticated_session()

    response = session.get(API_URL, params={
        "action": "query",
        "titles": page_name,
        "prop": "revisions",
        "rvprop": "content",
        "format": "json"
    })
    response.raise_for_status()
    data = response.json()
    
    pages = data.get("query", {}).get("pages", {})
    for page_id in pages:
        if page_id == "-1":
            return None
        # Return the content of the first revision
        revisions = pages[page_id].get("revisions", [])
        if revisions:
            return revisions[0].get("*", "")
    return None

US_GEO_SUFFIXES = {
    "Georgia", "Alabama", "Florida", "GA", "FL", "AL", "D.C.",
    "New Jersey", "NJ", "Washington", "WA", "Tennessee", "TN", "Texas", "TX"
}


def parse_categories(categories: Union[List[str], str, None]) -> list[str]:
    """Parse categories parameter into a clean list of category names."""
    if not categories:
        return []
    if isinstance(categories, (list, tuple, set)):
        return [str(c).strip() for c in categories if str(c).strip()]
    if isinstance(categories, str):
        cat_str = categories.strip()
        if not cat_str:
            return []
        if ";" in cat_str:
            raw_tokens = [c.strip() for c in cat_str.split(";") if c.strip()]
        elif "|" in cat_str:
            raw_tokens = [c.strip() for c in cat_str.split("|") if c.strip()]
        elif "\n" in cat_str:
            raw_tokens = [c.strip() for c in cat_str.splitlines() if c.strip()]
        else:
            try:
                reader = csv.reader([cat_str], skipinitialspace=True)
                raw_tokens = [c.strip() for c in next(reader) if c.strip()]
            except Exception:
                raw_tokens = [c.strip() for c in cat_str.split(",") if c.strip()]

        # Heal split geographic categories if comma split separated e.g. "Columbus", "Georgia"
        healed: list[str] = []
        i = 0
        while i < len(raw_tokens):
            tok = raw_tokens[i]
            if i + 1 < len(raw_tokens) and raw_tokens[i + 1] in US_GEO_SUFFIXES:
                healed.append(f"{tok}, {raw_tokens[i + 1]}")
                i += 2
            else:
                healed.append(tok)
                i += 1
        return healed
    return []


def _has_valid_opener(content: str, title: str) -> bool:
    """Check if content begins with a valid MediaWiki opener."""
    stripped = content.strip()
    if not stripped:
        return False
    if stripped.upper().startswith("#REDIRECT"):
        return True
    lines = stripped.splitlines()
    first_nonempty = next((l.strip() for l in lines if l.strip()), "")
    if first_nonempty.startswith("{{") or first_nonempty.startswith("''"):
        return True
    if first_nonempty.startswith("{|") or first_nonempty.startswith("==") or first_nonempty.startswith("<"):
        return True
    if first_nonempty.startswith("*") or first_nonempty.startswith("#"):
        return True
    if first_nonempty.startswith("'''"):
        return True
    return False


def build_page_content(page_name: str, categories: Union[List[str], str, None] = None, content_body: Optional[str] = None) -> str:
    """Construct complete, valid MediaWiki page content.

    Rules:
    - Never prepend a standalone bold title if content_body already has a valid opener.
    - If content_body starts with unbolded page_name, bold it into the lead sentence.
    - If content_body already contains {{bop}} or categories, preserve without duplication.
    - Normalize legacy {{baseOfPage}} to {{bop}}.
    - For Category: pages, omit {{bop}} and bold title opener.
    - For redirects and Scribunto modules, pass content verbatim.
    """
    # 1. Redirect
    if content_body and content_body.strip().upper().startswith("#REDIRECT"):
        return content_body.strip()

    # 2. Scribunto Module
    if page_name.startswith("Module:"):
        return content_body or ""

    is_category_page = page_name.startswith("Category:")

    # 3. Content body & Opener
    if content_body and content_body.strip():
        raw_content = content_body.strip()
        if is_category_page or _has_valid_opener(raw_content, page_name):
            content = raw_content
        elif raw_content.lower().startswith(page_name.lower()):
            match_len = len(page_name)
            content = f"'''{page_name}'''" + raw_content[match_len:]
        else:
            content = f"'''{page_name}'''\n\n{raw_content}"
    else:
        content = "" if is_category_page else f"'''{page_name}'''"

    # 4. Normalize legacy {{baseOfPage}} -> {{bop}}
    content = re.sub(r"\{\{baseOfPage\}\}", "{{bop}}", content, flags=re.IGNORECASE)

    # 5. Inspect existing {{bop}} and categories
    has_bop = bool(re.search(r"\{\{bop\}\}", content, flags=re.IGNORECASE))
    existing_cat_matches = re.findall(r"\[\[Category:\s*([^\]]+?)\s*\]\]", content, flags=re.IGNORECASE)
    existing_cats_normalized = {c.strip().replace('_', ' ').lower() for c in existing_cat_matches}

    # 6. Determine new categories to add
    category_list = parse_categories(categories)
    new_categories = [c for c in category_list if c.strip().replace('_', ' ').lower() not in existing_cats_normalized]

    # 7. Assemble final content
    if is_category_page:
        if new_categories:
            cat_block = "\n".join(f"[[Category:{c}]]" for c in new_categories)
            content = (content.rstrip() + "\n\n" + cat_block if content else cat_block) + "\n"
        elif content:
            content = content.rstrip() + "\n"
    else:
        if existing_cat_matches:
            if not has_bop:
                # Insert {{bop}} immediately above the first [[Category:
                m = re.search(r"\[\[Category:", content, flags=re.IGNORECASE)
                if m is not None:
                    idx = m.start()
                    prefix = content[:idx].rstrip()
                    suffix = content[idx:].strip()
                    content = prefix + "\n\n{{bop}}\n" + suffix
            if new_categories:
                cat_block = "\n".join(f"[[Category:{c}]]" for c in new_categories)
                content = content.rstrip() + "\n" + cat_block + "\n"
            else:
                content = content.rstrip() + "\n"
        else:
            if has_bop:
                if new_categories:
                    cat_block = "\n".join(f"[[Category:{c}]]" for c in new_categories)
                    content = content.rstrip() + "\n" + cat_block + "\n"
                else:
                    content = content.rstrip() + "\n"
            else:
                bop_and_cats = "{{bop}}\n" + "\n".join(f"[[Category:{c}]]" for c in new_categories)
                if content:
                    content = content.rstrip() + "\n\n" + bop_and_cats + "\n"
                else:
                    content = bop_and_cats + "\n"

    return content


def create_wwos_page(page_name, categories="", summary="Page created by script", content_body=None):
    """
    Creates or updates a page on the WWOS MediaWiki instance.
    
    Args:
        page_name: The title of the page to create/update
        categories: Comma/semicolon/pipe-separated string or list of categories
        summary: Edit summary for the change
        content_body: Optional body content for the page
    """
    session = get_authenticated_session()

    # 3. Get CSRF token for editing
    csrf_token_response = session.get(API_URL, params={
        "action": "query",
        "meta": "tokens",
        "format": "json"
    })
    csrf_token_response.raise_for_status()
    csrf_token = csrf_token_response.json()["query"]["tokens"]["csrftoken"]

    # 4. Construct page content
    content = build_page_content(page_name, categories, content_body)

    # 5. Create or update the page
    edit_data = {
        "action": "edit",
        "title": page_name,
        "text": content,
        "token": csrf_token,
        "format": "json",
        "summary": summary,
    }
    # Note: Omitting 'createonly' allows both creation and updates
    
    edit_response = session.post(API_URL, data=edit_data)
    edit_response.raise_for_status()
    
    result = edit_response.json()

    if "edit" in result and result["edit"].get("result") == "Success":
        page_id = result["edit"].get("pageid", "N/A")
        title = result["edit"].get("title", page_name)
        
        if "new" in result["edit"]:
            print(f"Successfully created page '{title}' (ID: {page_id})")
        elif "nochange" in result["edit"]:
            print(f"Page '{title}' unchanged (no edits needed)")
        else:
            print(f"Successfully updated page '{title}' (ID: {page_id})")
        return True
    elif "error" in result:
        print(f"API error: {result['error'].get('info', result['error'])}", file=sys.stderr)
        return False
    else:
        print(f"Unexpected response: {result}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Create or update a WWOS MediaWiki page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "My Page" "General"
  %(prog)s "My Page" "AI software, Tools, Projects"
  %(prog)s "My Page" "General" -c "This is the page content"
  %(prog)s "My Page" "General" -f content.txt -s "Updated from file"
        """
    )
    parser.add_argument("page_name", help="The name of the page to create/update")
    parser.add_argument("category", nargs="?", default="",
                        help="Category or delimited categories (optional if categories are in content)")
    parser.add_argument("-s", "--summary", default="Page created by automated script",
                        help="Edit summary (default: 'Page created by automated script')")
    parser.add_argument("-c", "--content", help="Content string for the page body")
    parser.add_argument("-f", "--content-file", help="Path to a file containing page content")
    
    args = parser.parse_args()

    # Check for password
    if not PASSWORD:
        print("Error: WWOS_PASSWORD environment variable not set.", file=sys.stderr)
        print("Set it with: export WWOS_PASSWORD='your_password'", file=sys.stderr)
        sys.exit(1)

    # Determine content source (file takes precedence)
    page_content = None
    if args.content_file:
        try:
            with open(args.content_file, 'r') as f:
                page_content = f.read()
        except FileNotFoundError:
            print(f"Error: Content file '{args.content_file}' not found.", file=sys.stderr)
            sys.exit(1)
        except IOError as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.content:
        page_content = args.content

    # Create/update the page
    success = create_wwos_page(
        page_name=args.page_name,
        categories=args.category,
        summary=args.summary,
        content_body=page_content
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
