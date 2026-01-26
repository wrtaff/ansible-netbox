#!/usr/bin/env python3
import argparse
import requests
import sys
import os
import re
from datetime import datetime
import urllib.parse

# Ensure local imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from create_wwos_page import create_wwos_page, page_exists, get_page_content
except ImportError:
    print("Error: Could not import 'create_wwos_page.py'. Make sure it is in the same directory.", file=sys.stderr)
    sys.exit(1)

WP_API_URL = "https://en.wikipedia.org/w/api.php"

def get_existing_categories(content):
    """
    Extracts existing categories from page content.
    Returns a set of category names.
    """
    # Regex to find [[Category:Name]] or [[Category:Name|SortKey]]
    # Case insensitive for 'Category'
    matches = re.findall(r'\[\[Category:\s*([^\]|]+)(?:\|.*)?\]\]', content, re.IGNORECASE)
    return {cat.strip() for cat in matches}

def get_wikipedia_content(url):
    """
    Fetches the Wikitext content of a Wikipedia page.
    """
    if "wikipedia.org/wiki/" not in url:
        raise ValueError("Invalid Wikipedia URL. Must contain 'wikipedia.org/wiki/'")
    
    # Extract title from URL
    title_slug = url.split("/wiki/")[-1]
    title = urllib.parse.unquote(title_slug).replace("_", " ")

    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "revisions|categories",
        "rvprop": "content",
        "cllimit": "max",
        "redirects": 1
    }
    
    headers = {
        "User-Agent": "GeminiCLI/1.0 (https://github.com/google/gemini-cli; gemini-cli@example.com)"
    }
    
    response = requests.get(WP_API_URL, params=params, headers=headers)
    response.raise_for_status()
    data = response.json()
    
    pages = data["query"]["pages"]
    page_id = list(pages.keys())[0]
    
    if page_id == "-1":
        raise ValueError(f"Page '{title}' not found on Wikipedia")
        
    revision = pages[page_id]["revisions"][0]
    content = revision["*"]
    real_title = pages[page_id]["title"]
    
    categories = []
    if "categories" in pages[page_id]:
        # Extract category titles, removing 'Category:' prefix
        for cat in pages[page_id]["categories"]:
            # Skip hidden categories
            if "hidden" in cat:
                continue
                
            cat_title = cat["title"]
            if cat_title.startswith("Category:"):
                cat_title = cat_title[9:]
            
            # Additional filtering for maintenance categories
            if any(cat_title.startswith(prefix) for prefix in [
                "Wikipedia", "Template", "Commons", "Articles", "Pages", "All ", "CS1"
            ]):
                continue
                
            categories.append(cat_title)
            
    return real_title, content, categories

def format_content(content, url):
    """
    Formats the Wikitext content for WWOS:
    1. Removes existing categories.
    2. Inserts citation after the first paragraph.
    """
    # 1. Remove existing categories (lines starting with [[Category:)
    content = re.sub(r'\[\[Category:[^]]+\]\]\n?', '', content, flags=re.IGNORECASE)
    
    # 2. Insert citation after first paragraph
    today = datetime.now().strftime("%Y-%m-%d")
    citation = f"<ref>{url} retrieved {today}</ref>"
    
    # Heuristic to find end of first paragraph:
    # Scan text, respecting template {{...}} and table {|...|} nesting.
    # The first double newline (\n\n) at nesting level 0 after some content is the break.
    
    i = 0
    length = len(content)
    brace_depth = 0
    table_depth = 0
    seen_content = False
    insertion_point = -1
    
    while i < length:
        # Check for templates {{ ... }}
        if content.startswith('{{', i):
            brace_depth += 1
            i += 2
            continue
        elif content.startswith('}}', i):
            if brace_depth > 0: brace_depth -= 1
            i += 2
            continue
            
        # Check for tables {| ... |}
        if content.startswith('{|', i):
            table_depth += 1
            i += 2
            continue
        elif content.startswith('|}', i):
            if table_depth > 0: table_depth -= 1
            i += 2
            continue
            
        # Check for double newline at root level
        if brace_depth == 0 and table_depth == 0:
            if content.startswith('\n\n', i):
                if seen_content:
                    insertion_point = i
                    break
            elif not content[i].isspace():
                # We found some non-whitespace content outside of templates
                seen_content = True
        
        i += 1
        
    if insertion_point != -1:
        # Insert citation before the double newline
        content = content[:insertion_point] + citation + content[insertion_point:]
    else:
        # If no double newline found, append to end
        content = content.rstrip() + citation + "\n\n"

    return content

def main():
    parser = argparse.ArgumentParser(description="Scrape Wikipedia and create WWOS page.")
    parser.add_argument("url", help="Wikipedia article URL")
    parser.add_argument("category", help="WWOS Category (comma separated)")
    parser.add_argument("-t", "--title", help="Override page title (default: Wikipedia title)")
    
    args = parser.parse_args()
    
    # Verify environment variable
    if not os.getenv("WWOS_PASSWORD"):
        print("Error: WWOS_PASSWORD environment variable not set.", file=sys.stderr)
        sys.exit(1)
    
    print(f"Fetching from {args.url}...")
    try:
        title, raw_content, wik_categories = get_wikipedia_content(args.url)
    except Exception as e:
        print(f"Error fetching Wikipedia content: {e}", file=sys.stderr)
        sys.exit(1)
        
    final_title = args.title if args.title else title
    
    print(f"Checking if '{final_title}' already exists on WWOS...")
    
    if page_exists(final_title):
        print(f"Page '{final_title}' already exists.")
        existing_content = get_page_content(final_title)
        existing_cats = get_existing_categories(existing_content)
        
        user_cats = {cat.strip() for cat in args.category.split(",") if cat.strip()}
        
        # Merge user categories with Wikipedia categories
        potential_cats = user_cats.union(set(wik_categories))
        
        # Determine which categories are new
        new_cats = potential_cats - existing_cats
        
        if not new_cats:
            print("No new categories to add. Exiting.")
            sys.exit(0)
            
        print(f"Automatically adding new categories: {', '.join(new_cats)}")
        
        # Append new categories to existing content
        updated_content = existing_content.rstrip() + "\n"
        for cat in new_cats:
            updated_content += f"[[Category:{cat}]]\n"
            
        from create_wwos_page import get_authenticated_session, API_URL
        
        session = get_authenticated_session()
        
        # Get CSRF token
        csrf_token_response = session.get(API_URL, params={
            "action": "query",
            "meta": "tokens",
            "format": "json"
        })
        csrf_token_response.raise_for_status()
        csrf_token = csrf_token_response.json()["query"]["tokens"]["csrftoken"]
        
        edit_data = {
            "action": "edit",
            "title": final_title,
            "text": updated_content,
            "token": csrf_token,
            "format": "json",
            "summary": f"Adding categories from Wikipedia: {', '.join(new_cats)}",
        }
        
        edit_response = session.post(API_URL, data=edit_data)
        edit_response.raise_for_status()
        result = edit_response.json()
        
        if "edit" in result and result["edit"].get("result") == "Success":
            print(f"Successfully added categories to '{final_title}'")
            sys.exit(0)
        else:
            print(f"Failed to update page: {result}", file=sys.stderr)
            sys.exit(1)

    print(f"Processing '{final_title}'...")
    formatted_content = format_content(raw_content, args.url)
    
    # Merge user categories with Wikipedia categories for NEW pages too
    user_cats = {cat.strip() for cat in args.category.split(",") if cat.strip()}
    all_cats_set = user_cats.union(set(wik_categories))
    combined_categories = ", ".join(all_cats_set)
    
    print(f"Creating WWOS page: {final_title} -> Categories: {combined_categories}")
    
    # Use existing create_wwos_page function
    success = create_wwos_page(
        page_name=final_title,
        categories=combined_categories,
        summary=f"Imported from {args.url}",
        content_body=formatted_content
    )
    
    if success:
        print("Done!")
        sys.exit(0)
    else:
        print("Failed to create page.", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
