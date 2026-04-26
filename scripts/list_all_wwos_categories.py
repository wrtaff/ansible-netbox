#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/list_all_wwos_categories.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-03-04

Purpose:
    Exhaustively lists all categories present on the WWOS MediaWiki using pagination.
================================================================================
"""
import requests
import os

API_URL = "http://wwos.home.arpa/api.php"
USERNAME = "will"
PASSWORD = os.getenv("WWOS_PASSWORD")

def get_categories(start_at=None):
    session = requests.Session()
    # Login
    login_token = session.get(API_URL, params={
        "action": "query", "meta": "tokens", "type": "login", "format": "json"
    }).json()["query"]["tokens"]["logintoken"]
    session.post(API_URL, data={
        "action": "login", "lgname": USERNAME, "lgpassword": PASSWORD, "lgtoken": login_token, "format": "json"
    })
    
    params = {
        "action": "query",
        "list": "allcategories",
        "aclimit": "max",
        "format": "json"
    }
    if start_at:
        params["acfrom"] = start_at
        
    response = session.get(API_URL, params=params).json()
    categories = [cat["*"] for cat in response.get("query", {}).get("allcategories", [])]
    return categories

if __name__ == "__main__":
    try:
        current = None
        all_cats = []
        while True:
            cats = get_categories(current)
            if not cats or (len(cats) == 1 and cats[0] == current):
                break
            all_cats.extend(cats)
            current = cats[-1]
            if len(cats) < 500:
                break
        
        # Unique categories
        unique_cats = sorted(list(set(all_cats)))
        for cat in unique_cats:
            print(cat)
    except Exception as e:
        print(f"Error: {e}")
