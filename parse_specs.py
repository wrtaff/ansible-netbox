import sys
from bs4 import BeautifulSoup

with open('/home/will/.gemini/antigravity-cli/brain/9cd4c365-59c7-4cba-a1ce-329b2409f897/.system_generated/steps/96/content.md', 'r') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')

with open('brother_specs.txt', 'w') as f:
    f.write(soup.get_text(separator='\n', strip=True))
