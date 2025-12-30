#!/usr/bin/env python3
"""
================================================================================
Filename:       update_wwos_page.py
Version:        2.3
Author:         Will
Last Modified:  2025-12-26

Purpose:
    Updates pages on the WWOS MediaWiki instance. The script handles
    authentication, CSRF token management, and page content formatting
    automatically. This version is specifically adapted to retrieve page
    content by ID, modify it, and then update the page.

Usage:
    # First, set your MediaWiki password as an environment variable:
    export WWOS_PASSWORD='your_password'

    # Example: Update a page with a specific ID and new content
    # ./update_wwos_page.py --page-id 12345 --content "Updated page text" --summary "Category change"

    # Example: Retrieve content, modify it, and push back (typical workflow for this agent)
    # 1. Get content:
    # content = get_wwos_page_content(page_id)
    # 2. Modify content (e.g., category replacement):
    # modified_content = content.replace("[[Category:Old]]", "[[Category:New]]")
    # 3. Update page:
    # update_wwos_page(page_id=12345, full_content=modified_content, summary="Updated category")


Arguments:
    --page-id           The ID of the wiki page to update.
    --page-name         The title of the wiki page to create or update (optional if --page-id is used for existing pages).
    --categories        Comma-separated string of categories to assign (optional, if full_content is provided).
    --full-content      The complete wikitext content to update the page with.
    -s, --summary       Edit summary (default: "Page updated by automated script")

Dependencies:
    - requests (pip install requests)

Exit Codes:
    0 - Success (page updated)
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
SESSION = requests.Session()


def _login():
    """Handles login to MediaWiki and stores session cookies."""
    if not PASSWORD:
        raise ValueError("WWOS_PASSWORD environment variable not set.")

    # 1. Get login token
    login_token_response = SESSION.get(API_URL, params={
        "action": "query",
        "meta": "tokens",
        "type": "login",
        "format": "json"
    })
    login_token_response.raise_for_status()
    login_token = login_token_response.json()["query"]["tokens"]["logintoken"]

    # 2. Login to get session cookies
    login_response = SESSION.post(API_URL, data={
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
    
    print("Successfully logged into MediaWiki.")


def _get_csrf_token():
    """Gets a CSRF token for editing actions."""
    csrf_token_response = SESSION.get(API_URL, params={
        "action": "query",
        "meta": "tokens",
        "format": "json"
    })
    csrf_token_response.raise_for_status()
    return csrf_token_response.json()["query"]["tokens"]["csrftoken"]


def get_wwos_page_content(page_id=None, page_name=None):
    """
    Retrieves the raw wikitext content of a page by its ID or title.
    
    Args:
        page_id: The ID of the page.
        page_name: The title of the page.

    Returns:
        The raw wikitext content as a string.
    
    Raises:
        ValueError: If neither page_id nor page_name is provided.
        Exception: If the page content cannot be retrieved or found.
    """
    if not page_id and not page_name:
        raise ValueError("Either page_id or page_name must be provided.")

    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "format": "json"
    }
    if page_id:
        params["pageids"] = page_id
    else:
        params["titles"] = page_name

    response = SESSION.get(API_URL, params=params)
    response.raise_for_status()
    data = response.json()

    pages = data.get("query", {}).get("pages", {})
    
    # MediaWiki API returns page IDs as keys, even if queried by title
    first_page_key = next(iter(pages), None)
    
    if first_page_key and first_page_key != "-1": # -1 indicates page not found
        content = pages[first_page_key].get("revisions", [{}])[0].get("*")
        if content is None:
            raise Exception(f"Could not retrieve content for page ID {page_id} / Title '{page_name}'")
        return content
    else:
        raise Exception(f"Page ID {page_id} / Title '{page_name}' not found.")


def update_wwos_page(page_id=None, page_name=None, full_content=None, categories=None, summary="Page updated by automated script"):
    """
    Updates a page on the WWOS MediaWiki instance.
    
    Args:
        page_id: The ID of the page to update.
        page_name: The title of the page to update (used if page_id is None).
        full_content: The complete wikitext content to replace the page with.
        categories: Comma-separated string of categories (used if full_content is None).
        summary: Edit summary for the change.
    """
    if not page_id and not page_name:
        raise ValueError("Either page_id or page_name must be provided to update a page.")
    
    _login() # Ensure logged in before getting CSRF token and editing
    csrf_token = _get_csrf_token()

    if full_content is None:
        # If full_content is not provided, we need to construct it from existing
        # content and new categories. This scenario is less likely for this
        # agent's current task but provides flexibility.
        existing_content = get_wwos_page_content(page_id=page_id, page_name=page_name)
        
        # Simple heuristic to find and replace existing categories or add new ones
        # This part might need more sophisticated parsing for complex cases.
        if categories:
            # Remove all existing category lines
            lines = existing_content.split('\n')
            new_lines = [line for line in lines if not line.strip().startswith('[[Category:')] # noqa
            content_to_edit = "\n".join(new_lines).strip() + "\n\n"

            # Add new categories
            category_list = [cat.strip() for cat in categories.split(",") if cat.strip()]
            for cat in category_list:
                content_to_edit += f"[[Category:{cat}]]\n"
            full_content = content_to_edit
        else:
            full_content = existing_content # No categories provided, just use existing content

    edit_data = {
        "action": "edit",
        "text": full_content,
        "token": csrf_token,
        "format": "json",
        "summary": summary,
        "bot": True # Mark as bot edit
    }
    if page_id:
        edit_data["pageid"] = page_id
    else:
        edit_data["title"] = page_name
    
    edit_response = SESSION.post(API_URL, data=edit_data)
    edit_response.raise_for_status()
    
    result = edit_response.json()

    if "edit" in result and result["edit"].get("result") == "Success":
        p_id = result["edit"].get("pageid", page_id)
        title = result["edit"].get("title", page_name)
        
        if "nochange" in result["edit"]:
            print(f"Page '{title}' (ID: {p_id}) unchanged (no edits needed)")
        else:
            print(f"Successfully updated page '{title}' (ID: {p_id})")
        return True
    elif "error" in result:
        print(f"API error: {result['error'].get('info', result['error'])}", file=sys.stderr)
        return False
    else:
        print(f"Unexpected response: {result}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Update a WWOS MediaWiki page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update a page by ID with specific content
  %(prog)s --page-id 12345 --full-content "New text for the page" --summary "Direct content update"

  # Change categories for a page by ID, preserving other content
  # (This typically requires fetching content first, modifying locally, then pushing back)
  # %(prog)s --page-id 12345 --categories "New Category, Another Category" --summary "Updated categories"
        """
    )
    parser.add_argument("--page-id", type=int, help="The ID of the page to update.")
    parser.add_argument("--page-name", help="The title of the page to update (used if --page-id is not provided for existing pages).")
    parser.add_argument("--full-content", help="The complete wikitext content to replace the page with.")
    parser.add_argument("--categories", help="Comma-separated string of categories to assign (used if --full-content is not provided).")
    parser.add_argument("-s", "--summary", default="Page updated by automated script",
                        help="Edit summary (default: 'Page updated by automated script')")
    
    args = parser.parse_args()

    # Check for password
    if not PASSWORD:
        print("Error: WWOS_PASSWORD environment variable not set.", file=sys.stderr)
        print("Set it with: export WWOS_PASSWORD='your_password'", file=sys.stderr)
        sys.exit(1)

    # Perform update
    try:
        success = update_wwos_page(
            page_id=args.page_id,
            page_name=args.page_name,
            full_content=args.full_content,
            categories=args.categories,
            summary=args.summary
        )
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"An error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
