#!/usr/bin/env python3
"""
================================================================================
Filename:       create_wwos.py
Version:        2.2
Author:         Will
Last Modified:  2025-12-12

Purpose:
    Creates or updates pages on the WWOS MediaWiki instance. The script handles
    authentication, CSRF token management, and page content formatting
    automatically. Pages are created with a standard structure including a
    bold title, optional body content, the {{baseOfPage}} template, and a
    category assignment.

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

# MediaWiki API endpoint and credentials
API_URL = "http://192.168.0.99/mediawiki/api.php"
USERNAME = "will"
PASSWORD = os.getenv("WWOS_PASSWORD")


def create_wwos_page(page_name, categories, summary="Page created by script", content_body=None):
    """
    Creates or updates a page on the WWOS MediaWiki instance.
    
    Args:
        page_name: The title of the page to create/update
        categories: Comma-separated string of categories to assign
        summary: Edit summary for the change
        content_body: Optional body content for the page
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

    # 3. Get CSRF token for editing
    csrf_token_response = session.get(API_URL, params={
        "action": "query",
        "meta": "tokens",
        "format": "json"
    })
    csrf_token_response.raise_for_status()
    csrf_token = csrf_token_response.json()["query"]["tokens"]["csrftoken"]

    # 4. Construct page content
    content = f"'''{page_name}'''\n\n"
    if content_body:
        content += content_body + "\n\n"
    content += "{{bop}}\n\n"
    
    # Parse and add multiple categories
    category_list = [cat.strip() for cat in categories.split(",") if cat.strip()]
    for cat in category_list:
        content += f"[[Category:{cat}]]\n"

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
    parser.add_argument("category", 
                        help="Category or comma-separated categories (e.g., 'General' or 'AI software, Tools')")
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
