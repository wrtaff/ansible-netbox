import argparse
import requests
import sys

def get_wwos_page(page_title):
    url = "http://192.168.0.99/mediawiki/api.php"
    params = {
        "action": "parse",
        "page": page_title,
        "format": "json",
        "prop": "wikitext"
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if "error" in data:
            print(f"Error: {data['error']['info']}", file=sys.stderr)
            sys.exit(1)
            
        if "parse" in data and "wikitext" in data["parse"]:
            print(data["parse"]["wikitext"]["*"])
        else:
            print(f"Page '{page_title}' not found or no wikitext.", file=sys.stderr)
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"Network error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch WWOS (MediaWiki) page content.")
    parser.add_argument("page_title", help="Title of the page to fetch")
    args = parser.parse_args()
    
    get_wwos_page(args.page_title)
