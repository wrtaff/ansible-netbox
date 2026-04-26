#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/get_wwos_category_info.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-03-04

Purpose:
    Retrieves the content of a specific Category page on WWOS MediaWiki.
================================================================================
"""
import requests
import os

API_URL = "http://wwos.home.arpa/api.php"
USERNAME = "will"
PASSWORD = os.getenv("WWOS_PASSWORD")

def get_category_info(cat_name):
    session = requests.Session()
    # Login
    login_token = session.get(API_URL, params={
        "action": "query", "meta": "tokens", "type": "login", "format": "json"
    }).json()["query"]["tokens"]["logintoken"]
    session.post(API_URL, data={
        "action": "login", "lgname": USERNAME, "lgpassword": PASSWORD, "lgtoken": login_token, "format": "json"
    })
    
    # Get page content for Category:Name
    params = {
        "action": "query",
        "titles": f"Category:{cat_name}",
        "prop": "revisions",
        "rvprop": "content",
        "format": "json"
    }
    response = session.get(API_URL, params=params).json()
    pages = response.get("query", {}).get("pages", {})
    for page_id in pages:
        if page_id == "-1":
            return None
        return pages[page_id].get("revisions", [])[0].get("*", "")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        print(get_category_info(sys.argv[1]))
