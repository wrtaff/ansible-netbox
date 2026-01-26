import json

# Load the JSON data from the file
try:
    with open('tmp/google_antigravity_page.json', 'r') as f:
        data = json.load(f)
except (IOError, json.JSONDecodeError) as e:
    print(f"Error reading or parsing JSON file: {e}")
    exit(1)

# Extract the wikitext content
try:
    page_id = list(data['query']['pages'].keys())[0]
    content = data['query']['pages'][page_id]['revisions'][0]['*']
except (KeyError, IndexError):
    print("Error: Could not find page content in the JSON structure.")
    exit(1)

# Define the new citation based on the user's bookmarklet format
new_citation = '"An agentic development platform that evolves the IDE into an agent-first era." <ref>https://antigravity.google/ retrieved 2025-12-11</ref>'

# 1. Find the content of the first paragraph to identify where to put the main citation.
# This makes the replacement more robust than just replacing the first '[1]'.
first_paragraph_end = content.find('\n\n')
if first_paragraph_end != -1:
    # Replace the '[1]' in the first paragraph only
    first_paragraph = content[:first_paragraph_end]
    rest_of_content = content[first_paragraph_end:]
    updated_first_paragraph = first_paragraph.replace('[1]', new_citation)
    content = updated_first_paragraph + rest_of_content
else:
    # If there's no double newline, just replace the first instance in the whole doc
    content = content.replace('[1]', new_citation, 1)

# 2. Remove all other instances of the old citation marker
content = content.replace('[1]', '')

# 3. Remove the old "Sources:" section if it exists
if 'Sources:' in content:
    content = content.split('Sources:')[0].strip()

# Save the updated content to a new file
try:
    with open('tmp/google_antigravity_content_updated.txt', 'w') as f:
        f.write(content)
    print("Successfully updated content and saved to tmp/google_antigravity_content_updated.txt")
except IOError as e:
    print(f"Error writing to output file: {e}")
    exit(1)
