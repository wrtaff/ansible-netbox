#!/usr/bin/env python3
import subprocess
import re
import os
import sys
import datetime
import urllib.request
import urllib.error
import json

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
    except Exception as e:
        print(f"Error requesting {url}: {e}")
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
    payload = {
        "from_date": date_str,
        "to_date": date_str,
        "meal_type": {"id": meal_type_id, "name": DEFAULT_MEAL_TYPE_NAME},
        "title": title,
        "note": "",
        "recipe": None,
        "servings": 1
    }
    response = make_request("meal-plan", write_token, method="POST", data=payload)
    return response is not None

def extract_recipes_from_pdf(pdf_path):
    try:
        result = subprocess.run(['pdftotext', pdf_path, '-'], capture_output=True, text=True, check=True)
        text = result.stdout
    except Exception as e:
        print(f"Error running pdftotext: {e}")
        return []

    recipes = []
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    i = 0
    while i < len(lines):
        line = lines[i]
        # Look for duration line (e.g. "28 min.")
        if re.match(r'^\d+\s*min\.', line):
            # The title is almost ALWAYS the next line
            if i + 1 < len(lines):
                title = lines[i+1]
                # Filter out obvious junk
                if not any(k in title for k in ["cals.", "serv.", "HUNGRYROOT", "View + rate"]):
                    # Clean up
                    title = re.sub(r'\(Edited\)', '', title).strip()
                    title = re.sub(r'[\+\s]+$', '', title).strip()
                    if title and title not in recipes:
                        recipes.append(title)
        i += 1

    return recipes

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
    if len(sys.argv) < 2:
        print("Usage: ./import_hungryroot_meals.py <path_to_pdf>")
        sys.exit(1)
        
    pdf_path = sys.argv[1]
    
    read_token, write_token = get_tokens()
    
    if not read_token or not write_token:
        print("Error: TANDOOR_API_READ_TOKEN and TANDOOR_API_WRITE_TOKEN must be set,")
        print("or 'auth_config.json' must exist with 'read_token' and 'write_token'.")
        sys.exit(1)

    print(f"Processing PDF: {pdf_path}")
    recipes = extract_recipes_from_pdf(pdf_path)
    
    if not recipes:
        print("No recipes found in PDF.")
        sys.exit(1)
        
    print("\nExtracted Recipes:")
    for i, r in enumerate(recipes):
        print(f"  {i+1}. {r}")
        
    print("\nOptions:")
    print("  y: Import all")
    print("  e: Edit list")
    print("  n: Abort")
    
    # Check if we are in a non-interactive environment
    if not sys.stdin.isatty():
        print("Non-interactive mode: proceeding with 'y'")
        choice = 'y'
    else:
        choice = input("\nChoice: ").strip().lower()
    
    if choice == 'e':
        print("Enter recipe titles one per line. Empty line to finish.")
        new_recipes = []
        while True:
            r = input("> ").strip()
            if not r:
                break
            new_recipes.append(r)
        if new_recipes:
            recipes = new_recipes
        choice = 'y'

    if choice != 'y':
        print("Aborted.")
        sys.exit(0)
        
    meal_type_id = get_meal_type_id(read_token, DEFAULT_MEAL_TYPE_NAME)
    if not meal_type_id:
        print("Could not find meal type ID.")
        sys.exit(1)
        
    start_date = datetime.date.today()
    for i, title in enumerate(recipes):
        target_date = start_date + datetime.timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        print(f"Adding '{title}' for {date_str}...")
        if add_meal_to_plan(write_token, title, date_str, meal_type_id):
            print("  Success.")
        else:
            print("  Failed.")

if __name__ == "__main__":
    main()