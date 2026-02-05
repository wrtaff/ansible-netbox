"""
================================================================================
Filename:       perform_wwos_update.py
Version:        1.1
Author:         Gemini CLI
Last Modified:  2026-02-05
Context:        http://trac.home.arpa/ticket/3035

Purpose:
    A helper script to update WWOS pages by prepending new content.
    
    Update 1.1:
    - Refactored to accept page_name and content file as arguments.
================================================================================
"""
import subprocess
import sys
import argparse

parser = argparse.ArgumentParser(description="Update a WWOS page by prepending content.")
parser.add_argument("page_name", help="The name of the page to update.")
parser.add_argument("-f", "--file", required=True, help="File containing the new content to prepend.")
args = parser.parse_args()

page_name = args.page_name
with open(args.file, 'r') as f:
    new_section = f.read()

# Fetch existing content
cmd_get = ["python3", "scripts/get_wwos_page.py", page_name]
result = subprocess.run(cmd_get, capture_output=True, text=True)
if result.returncode != 0:
    print(f"Error fetching page: {result.stderr}")
    sys.exit(1)

content = result.stdout.strip()

# Find the end (Categories) to insert before, or just append if no categories found
# But standard is usually before {{baseOfPage}} or categories.
# The content has {{baseOfPage}}.
marker = "{{baseOfPage}}"
if marker in content:
    parts = content.split(marker)
    new_content = parts[0] + new_section + "\n" + marker + parts[1]
else:
    new_content = content + "\n" + new_section

# Write to temp file for the update script
import os
with open("tmp/wwos_update.txt", "w") as f:
    f.write(new_content)

# Update the page
# We use shell=True for the script call to handle arguments easily, or list
cmd_update = [
    "python3", "scripts/update_wwos_page.py",
    "--page-name", page_name,
    "--full-content", new_content,
    "--summary", "Added Deployment 2026 details"
]

# We need to pass the content as an argument, which might be large.
# Ideally the script would take a file input, but it takes --full-content arg.
# Let's hope it's not too long for the shell.
# Alternatively, I can modify update_wwos_page.py to take a file, but I shouldn't modify tools if I can avoid it.
# Wait, I see I modified update_trac_ticket.py.
# Actually, the user's tool `update_wwos_page.py` uses `argparse`.
# If the content is large, `subprocess.run` with list of args is safer than shell=True.
# So I will use `subprocess.run(cmd_update)`.

result_update = subprocess.run(cmd_update, capture_output=True, text=True)
print(result_update.stdout)
print(result_update.stderr)