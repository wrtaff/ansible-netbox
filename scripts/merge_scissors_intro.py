import sys
import re
import requests
from datetime import datetime
from scripts.create_wwos_page import get_page_content, get_authenticated_session, API_URL

WP_API_URL = "https://en.wikipedia.org/w/api.php"
PAGE_TITLE = "Scissors"
WIK_URL = "https://en.wikipedia.org/wiki/Scissors"

def get_wikipedia_intro(title):
    params = {
        "action": "query",
        "format": "json",
        "titles": title,
        "prop": "extracts",
        "explaintext": True,  # Get plain text, not HTML
        "exintro": True,      # Only the intro
        "redirects": 1
    }
    headers = {"User-Agent": "GeminiCLI/1.0"}
    response = requests.get(WP_API_URL, params=params, headers=headers)
    data = response.json()
    page = next(iter(data["query"]["pages"].values()))
    return page["extract"]

def main():
    print(f"Fetching current WWOS content for '{PAGE_TITLE}'...")
    current_content = get_page_content(PAGE_TITLE)
    if not current_content:
        print(f"Error: Page '{PAGE_TITLE}' not found on WWOS.")
        sys.exit(1)

    print(f"Fetching Wikipedia intro for '{PAGE_TITLE}'...")
    wik_intro = get_wikipedia_intro("Scissors")
    
    # Split into paragraphs and take top 3
    paragraphs = [p for p in wik_intro.split('\n\n') if p.strip()]
    top_3_paragraphs = "\n\n".join(paragraphs[:3])
    
    # Create citation
    today = datetime.now().strftime("%Y-%m-%d")
    citation = f"<ref>{WIK_URL} retrieved {today}</ref>"
    
    # Combine: New Intro + Citation + Old Content
    # We'll put the new intro at the top, then the citation.
    # We should probably strip the old content of any existing {{bop}} or similar if it duplicates,
    # but "no loss of info" implies we keep it all.
    
    # Format:
    # '''Scissors''' (Wikipedia Intro)
    # <ref>...</ref>
    #
    # (Original Content)
    
    new_content = f"{top_3_paragraphs}{citation}\n\n{current_content}"
    
    print("Updating page...")
    session = get_authenticated_session()
    csrf_token = session.get(API_URL, params={
        "action": "query", "meta": "tokens", "format": "json"
    }).json()["query"]["tokens"]["csrftoken"]
    
    edit_response = session.post(API_URL, data={
        "action": "edit",
        "title": PAGE_TITLE,
        "text": new_content,
        "token": csrf_token,
        "format": "json",
        "summary": "Prepending Wikipedia intro (first 3 paras)"
    })
    
    print(edit_response.json())

if __name__ == "__main__":
    main()
