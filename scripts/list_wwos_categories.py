#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/list_wwos_categories.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-03-04

Purpose:
    Lists categories from WWOS MediaWiki (limited to first 500).
================================================================================
"""
import requests
import os

API_URL = "http://192.168.0.99/mediawiki/api.php"
USERNAME = "will"
PASSWORD = os.getenv("WWOS_PASSWORD")

def get_categories():
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
    
    # List categories
    params = {
        "action": "query",
        "list": "allcategories",
        "aclimit": "500",
        "format": "json"
    }
    response = session.get(API_URL, params=params).json()
    categories = [cat["*"] for cat in response.get("query", {}).get("allcategories", [])]
    return categories

if __name__ == "__main__":
    try:
        if not PASSWORD:
            print("Error: WWOS_PASSWORD not set.")
            exit(1)
        cats = get_categories()
        for cat in cats:
            print(cat)
    except Exception as e:
        print(f"Error: {e}")
