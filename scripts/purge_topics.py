#!/usr/bin/env python3
"""
================================================================================
Filename:       purge_topics.py
Version:        1.0
Author:         Gemini CLI
Last Modified:  2026-06-16
Context:        http://trac.home.arpa/ticket/3627

Purpose:
    Connects to the FreshRSS Google Reader API to pull unread items from a category.
    Uses Gemini (via REST API) to find all articles related to a user-provided topic,
    summarizes them, and marks them all as read to purge them from the feed.

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
    resp = requests.post(LOGIN_URL, data={"Email": username, "Passwd": password})
    resp.raise_for_status()
    for line in resp.text.split("\n"):
        if line.startswith("Auth="):
            return line.split("=", 1)[1]
    raise Exception("Auth token not found in FreshRSS response")

def get_unread_items(auth_token, category, limit=250):
    print(f"Fetching up to {limit} unread items for category: {category}...")
    headers = {"Authorization": f"GoogleLogin auth={auth_token}"}
    params = {
        "output": "json",
        "n": limit,
        "xt": "user/-/state/com.google/read",
        "s": f"user/-/label/{category}"
    }
    resp = requests.get(f"{API_URL}/stream/contents/", headers=headers, params=params)
    resp.raise_for_status()
    return resp.json().get("items", [])

def mark_as_read(auth_token, item_ids):
    if not item_ids:
        return
    print(f"Marking {len(item_ids)} items as read...")
    headers = {"Authorization": f"GoogleLogin auth={auth_token}"}
    
    resp = requests.get(f"{API_URL}/token", headers=headers)
    resp.raise_for_status()
    action_token = resp.text

    data = [
        ("T", action_token),
        ("a", "user/-/state/com.google/read")
    ]
    for item_id in item_ids:
        data.append(("i", item_id))
        
    resp = requests.post(f"{API_URL}/edit-tag", headers=headers, data=data)
    resp.raise_for_status()
    print("Successfully marked items as read.")

def process_with_llm(items, topic):
    print(f"Analyzing {len(items)} articles with Gemini to find '{topic}' content...")
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
        summary = summary[:500] 
        
        articles_payload += f"--- ARTICLE {idx} ---\nID: {item['id']}\nTitle: {title}\nSummary: {summary}\n\n"

    prompt = f"""
You are an intelligent RSS assistant. Analyze the following articles.
Your job is to:
1. Identify all articles that are about or strongly related to the following topic: {topic}
2. Write a brief summary of the news contained in these identified articles.
3. Return a JSON structure exactly matching this format:

{{
  "topic_summary": "A cohesive summary of all the headlines related to '{topic}' found in the feed...",
  "target_article_ids": ["id_1", "id_2", "id_3"] // The IDs of ONLY the articles related to the topic
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
    parser = argparse.ArgumentParser(description="Purge and summarize specific topics.")
    parser.add_argument("--category", default="Nation World")
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--topic", required=True, help="Topic to find and purge")
    args = parser.parse_args()

    auth_token = login(get_env_var("FRESHRSS_USER"), get_env_var("FRESHRSS_PASSWORD"))
    items = get_unread_items(auth_token, args.category, args.limit)
    
    if not items:
        print(f"No unread items found for category '{args.category}'.")
        return

    analysis = process_with_llm(items, args.topic)
    
    print("\n--- TOPIC SUMMARY ---")
    print(analysis.get("topic_summary", f"No {args.topic} news found."))
    
    to_mark_read = analysis.get("target_article_ids", [])
    if to_mark_read:
        mark_as_read(auth_token, to_mark_read)
    else:
        print("\nNo items found to mark as read.")

if __name__ == "__main__":
    main()
