import requests
import json
import re
import collections
import sys
import os
from datetime import datetime, timedelta

# Configuration - should ideally be moved to env vars or vault-loaded config
GRAYLOG_URL = "http://192.168.0.104:9000"
API_TOKEN = os.environ.get("GRAYLOG_API_TOKEN", "your_token_here")

def norm(m):
    """Normalize message patterns to identify unique issues while collapsing noise."""
    m = re.sub(r'\b\d{1,3}(\.\d{1,3}){3}\b', '<IP>', m)
    m = re.sub(r'port \d+', 'port <N>', m)
    m = re.sub(r'\[\d+\]', '[[<PID>]]', m)
    m = re.sub(r'pid=\d+', 'pid=<PID>', m)
    m = re.sub(r'\b[0-9a-f]{8,}\b', '<HEX>', m, flags=re.I)
    m = re.sub(r'audit\(\d+\.\d+:\d+\)', 'audit(<TIMESTAMP>:<ID>)', m)
    return m.strip()

def query_graylog(query="*", range_seconds=86400, limit=5000):
    """Query Graylog API for logs in a relative time range."""
    endpoint = f"{GRAYLOG_URL}/api/search/universal/relative"
    
    headers = {
        "Accept": "application/json",
        "X-Requested-By": "pops-agent"
    }
    
    params = {
        "query": query,
        "range": range_seconds,
        "limit": limit,
        "fields": "timestamp,source,message",
        "sort": "timestamp:desc"
    }
    
    try:
        response = requests.get(
            endpoint,
            auth=(API_TOKEN, "token"),
            headers=headers,
            params=params,
            timeout=30
        )
        
        response.raise_for_status()
        data = response.json()
        
        messages = data.get('messages', [])
        return [m['message'] for m in messages]
            
    except requests.exceptions.RequestException as e:
        print(f"Error querying Graylog: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return []

def print_report(rows):
    """Generate the standardized top-N frequency report."""
    if not rows:
        print("No messages found.")
        return

    pats = collections.Counter(norm(r.get('message', '')) for r in rows)
    ex = {norm(r.get('message', '')): (r.get('source', 'unknown'), r.get('message', '')) for r in reversed(rows)}
    
    print(f"--- Graylog 24h Summary ({len(rows)} messages) ---")
    for p, c in pats.most_common(30):
        src, msg = ex[p]
        print(f'[{c}x][{src}] {msg[:180]}')

if __name__ == "__main__":
    # Default to 24h report
    results = query_graylog()
    print_report(results)
