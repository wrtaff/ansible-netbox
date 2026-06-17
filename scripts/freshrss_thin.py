#!/usr/bin/env python3
"""
================================================================================
Filename:       freshrss_thin.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-06-16
Context:        http://trac.home.arpa/ticket/3627

Purpose:
    Connects to the FreshRSS Google Reader API to pull unread items from a category.
    Uses Gemini (via REST API) to cluster duplicate articles covering the same event,
    picks a primary article, and marks the redundant ones as read.

Secrets:
    FRESHRSS_USER       (Env Var) — Username for FreshRSS Google Reader API
    FRESHRSS_PASSWORD   (Env Var) — API Password for FreshRSS Google Reader API
    GEMINI_API_KEY      (Env Var) — API key for Google Gemini model access
================================================================================
"""
import os
import requests
import json
import argparse
import sys


# FreshRSS Google Reader API Configuration
BASE_URL = "https://ynh2.van-bee.ts.net/freshrss/api/greader.php"
LOGIN_URL = f"{BASE_URL}/accounts/ClientLogin"
API_URL = f"{BASE_URL}/reader/api/0"

def get_env_var(name):
    val = os.getenv(name)
    if not val:
        print(f"Error: Environment variable {name} is required.")
        sys.exit(1)
    return val

def login(username, password):
    print("Logging into FreshRSS...")
    resp = requests.post(LOGIN_URL, data={
        "Email": username,
        "Passwd": password
    })
    resp.raise_for_status()
    for line in resp.text.split("\n"):
        if line.startswith("Auth="):
            return line.split("=", 1)[1]
    raise Exception("Auth token not found in FreshRSS response")

def get_unread_items(auth_token, category, limit=50):
    print(f"Fetching unread items for category: {category}...")
    headers = {"Authorization": f"GoogleLogin auth={auth_token}"}
    params = {
        "output": "json",
        "n": limit,
        "xt": "user/-/state/com.google/read",
    }
    if category:
        params["s"] = f"user/-/label/{category}"
        
    resp = requests.get(f"{API_URL}/stream/contents/", headers=headers, params=params)
    resp.raise_for_status()
    return resp.json().get("items", [])

def mark_as_read(auth_token, item_ids):
    if not item_ids:
        return
    print(f"Marking {len(item_ids)} items as read...")
    headers = {"Authorization": f"GoogleLogin auth={auth_token}"}
    
    # Get the required action token
    resp = requests.get(f"{API_URL}/token", headers=headers)
    resp.raise_for_status()
    action_token = resp.text

    # Google Reader API requires multiple 'i' parameters for bulk edits
    data = [
        ("T", action_token),
        ("a", "user/-/state/com.google/read")
    ]
    for item_id in item_ids:
        data.append(("i", item_id))
        
    resp = requests.post(f"{API_URL}/edit-tag", headers=headers, data=data)
    resp.raise_for_status()
    print("Successfully marked items as read.")

def process_with_llm(items):
    print(f"Analyzing {len(items)} articles with Gemini...")
    api_key = get_env_var("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    # Prepare payload
    articles_payload = ""
    for idx, item in enumerate(items):
        title = item.get("title", "No Title")
        summary = item.get("summary", {}).get("content", "")
        if not summary:
            summary = item.get("content", {}).get("content", "No Content")
        
        # Truncate content to avoid huge context usage
        summary = summary[:1000] 
        
        articles_payload += f"--- ARTICLE {idx} ---\nID: {item['id']}\nTitle: {title}\nSummary: {summary}\n\n"

    prompt = f"""
You are an intelligent RSS aggregator. Analyze the following articles from a feed category.
Your job is to:
1. Group articles that cover the exact same subject/event.
2. For each group, pick one article as the "primary" and summarize the event.
3. List the remaining articles in the group as "redundant".
4. Return a JSON structure exactly matching this format:

{{
  "summary": "A brief overview of all unique topics currently in the feed...",
  "topics": [
    {{
      "topic_name": "Topic title",
      "summary": "1-2 sentence summary of this topic.",
      "primary_article_id": "id_of_the_chosen_primary_article",
      "redundant_article_ids": ["id_1", "id_2"]
    }}
  ],
  "unrelated_articles": ["id_x", "id_y"] // IDs of articles that don't share a topic and should be kept unread
}}

Here are the articles:
{articles_payload}
"""
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    
    resp = requests.post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    
    try:
        text_output = data['candidates'][0]['content']['parts'][0]['text']
        return json.loads(text_output)
    except Exception as e:
        print(f"Failed to parse LLM output: {data}")
        raise e

def main():
    parser = argparse.ArgumentParser(description="Summarize and thin a FreshRSS category using AI.")
    parser.add_argument("--category", required=True, help="Category name (e.g., 'Sports')")
    parser.add_argument("--limit", type=int, default=50, help="Max articles to fetch")
    parser.add_argument("--dry-run", action="store_true", help="Print summary but do not mark anything as read")
    args = parser.parse_args()

    freshrss_user = get_env_var("FRESHRSS_USER")
    freshrss_pass = get_env_var("FRESHRSS_PASSWORD")
    
    auth_token = login(freshrss_user, freshrss_pass)
    items = get_unread_items(auth_token, args.category, args.limit)
    
    if not items:
        print(f"No unread items found for category '{args.category}'.")
        return

    analysis = process_with_llm(items)
    
    print("\n--- CATEGORY SUMMARY ---")
    print(analysis.get("summary", ""))
    print("\n--- TOPICS ---")
    for t in analysis.get("topics", []):
        print(f"\n* {t.get('topic_name')} *")
        print(t.get('summary'))
        print(f"  Primary ID retained: {t.get('primary_article_id')}")
        print(f"  Redundant IDs to clear: {len(t.get('redundant_article_ids', []))} articles")
    
    # Collect IDs to mark as read
    to_mark_read = []
    for t in analysis.get("topics", []):
        to_mark_read.extend(t.get('redundant_article_ids', []))
        
    if to_mark_read:
        if args.dry_run:
            print(f"\n[DRY RUN] Would mark {len(to_mark_read)} items as read: {to_mark_read}")
        else:
            mark_as_read(auth_token, to_mark_read)
    else:
        print("\nNo redundant items to thin.")

if __name__ == "__main__":
    main()
