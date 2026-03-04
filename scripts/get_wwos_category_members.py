#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/get_wwos_category_members.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-03-04

Purpose:
    Lists all members (pages) belonging to a specific Category on WWOS MediaWiki.
================================================================================
"""
import requests
import os

API_URL = "http://192.168.0.99/mediawiki/api.php"
USERNAME = "will"
PASSWORD = os.getenv("WWOS_PASSWORD")

def get_category_members(cat_name):
    session = requests.Session()
    # Login
    login_token = session.get(API_URL, params={
        "action": "query", "meta": "tokens", "type": "login", "format": "json"
    }).json()["query"]["tokens"]["logintoken"]
    session.post(API_URL, data={
        "action": "login", "lgname": USERNAME, "lgpassword": PASSWORD, "lgtoken": login_token, "format": "json"
    })
    
    # List members
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": f"Category:{cat_name}",
        "cmlimit": "max",
        "format": "json"
    }
    response = session.get(API_URL, params=params).json()
    members = [m["title"] for m in response.get("query", {}).get("categorymembers", [])]
    return members

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        members = get_category_members(sys.argv[1])
        for m in members:
            print(m)
