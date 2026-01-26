#!/usr/bin/env python3
import urllib.request
import urllib.error
import urllib.parse
import json
import os
import sys
import datetime

# Configuration
BASE_URL = "http://tandoor.home.arpa/api"
DEFAULT_MEAL_TYPE_NAME = "Supper"

def get_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def make_request(endpoint, token, method="GET", data=None):
    url = f"{BASE_URL}/{endpoint}/" 
    headers = get_headers(token)
    
    if data:
        json_data = json.dumps(data).encode('utf-8')
    else:
        json_data = None

    req = urllib.request.Request(url, data=json_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 204:
                return None
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        # Silently fail for discovery, but print details if it's the final POST
        if method == "POST":
            print(f"HTTP Error {e.code} accessing {url}: {e.reason}")
            try:
                print(f"Server response: {e.read().decode()}")
            except:
                pass
        return None
    except urllib.error.URLError as e:
        if method == "POST":
            print(f"URL Error accessing {url}: {e.reason}")
        return None

def get_meal_type_id(read_token, type_name):
    response = make_request("meal-type", read_token)
    if response:
        results = response.get('results', response) if isinstance(response, dict) else response
        if isinstance(results, list):
            for mt in results:
                if mt.get('name', '').lower() == type_name.lower():
                    return mt.get('id')
    return None

def add_meal_to_plan(write_token, title, date_str, meal_type_id):
    # Payload for a "Note" based meal plan entry
    payload = {
        "from_date": date_str,
        "to_date": date_str,
        "meal_type": {"id": meal_type_id, "name": DEFAULT_MEAL_TYPE_NAME},
        "title": title,
        "note": "",
        "recipe": None,
        "servings": 1
    }
    
    print(f"Attempting to add meal '{title}' to {date_str} (Meal Type ID: {meal_type_id})...")
    response = make_request("meal-plan", write_token, method="POST", data=payload)
    
    if response and ('id' in response or response == None):
        return True
    return False

def get_tokens():
    read_token = os.environ.get("TANDOOR_API_READ_TOKEN")
    write_token = os.environ.get("TANDOOR_API_WRITE_TOKEN")
    
    if read_token and write_token:
        return read_token, write_token
        
    config_path = os.path.join(os.path.dirname(__file__), "auth_config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                read_token = config.get("read_token") or read_token
                write_token = config.get("write_token") or write_token
        except Exception as e:
            print(f"Warning: Failed to read auth_config.json: {e}")
            
    return read_token, write_token

def main():
    # 1. Get Tokens
    read_token, write_token = get_tokens()
    
    if not read_token or not write_token:
        print("Error: TANDOOR_API_READ_TOKEN and TANDOOR_API_WRITE_TOKEN environment variables must be set,")
        print("or 'auth_config.json' must exist with 'read_token' and 'write_token'.")
        sys.exit(1)

    # 2. Get Meal Title from args or input
    if len(sys.argv) > 1:
        title = " ".join(sys.argv[1:])
    else:
        title = input("Enter meal title: ").strip()
    
    if not title:
        print("Title is required.")
        sys.exit(1)
        
    today = datetime.date.today().strftime("%Y-%m-%d")
    
    # 3. Find Meal Type ID (using read token)
    meal_type_id = get_meal_type_id(read_token, DEFAULT_MEAL_TYPE_NAME)
    
    if not meal_type_id:
        print(f"Could not find meal type '{DEFAULT_MEAL_TYPE_NAME}'.")
        sys.exit(1)
    
    # 4. Add Meal (using write token)
    success = add_meal_to_plan(write_token, title, today, meal_type_id)
    if success:
        print(f"Successfully added '{title}' to today's plan!")
    else:
        print("Failed to add meal.")
        sys.exit(1)

if __name__ == "__main__":
    main()