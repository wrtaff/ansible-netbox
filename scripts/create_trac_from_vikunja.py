#!/usr/bin/env python3
import argparse
import requests
import json
import subprocess
import os
import sys
from xml.sax.saxutils import escape

# Configuration
VIKUNJA_URL = os.getenv("VIKUNJA_URL", "http://todo.home.arpa")
VIKUNJA_API_TOKEN = os.getenv("VIKUNJA_API_TOKEN")
TRAC_URL = os.getenv("TRAC_URL", "http://trac-lxc.home.arpa/login/xmlrpc")
TRAC_PUBLIC_URL_BASE = os.getenv("TRAC_PUBLIC_URL_BASE", "http://trac.gafla.us.com/ticket")
TRAC_USER = os.getenv("TRAC_USER", "will")
TRAC_PASS = os.getenv("TRAC_PASSWORD")
TEMP_DIR = "tmp"

if not VIKUNJA_API_TOKEN:
    print("Error: VIKUNJA_API_TOKEN environment variable not set.")
    sys.exit(1)

if not TRAC_PASS:
    print("Error: TRAC_PASSWORD environment variable not set.")
    sys.exit(1)

def get_vikunja_task(task_id):
    headers = {
        "Authorization": f"Bearer {VIKUNJA_API_TOKEN}"
    }
    url = f"{VIKUNJA_URL}/api/v1/tasks/{task_id}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Vikunja task {task_id}: {e}")
        sys.exit(1)

def update_vikunja_task(task_id, description_with_link):
    headers = {
        "Authorization": f"Bearer {VIKUNJA_API_TOKEN}",
        "Content-Type": "application/json"
    }
    url = f"{VIKUNJA_URL}/api/v1/tasks/{task_id}"
    try:
        # Vikunja uses POST to update specific fields of a task
        response = requests.post(url, headers=headers, json={"description": description_with_link})
        response.raise_for_status()
        print(f"Successfully updated Vikunja Task {task_id} description with Trac link.")
    except requests.exceptions.RequestException as e:
        print(f"Error updating Vikunja task {task_id}: {e}")

def create_trac_ticket_xml(summary, description, component, priority, keywords):
    # Construct XML payload manually to ensure correct structure for Trac XML-RPC
    # ticket.create(summary, description, {attributes}, notify=true)
    
    xml_content = f"""<?xml version="1.0"?>
<methodCall>
<methodName>ticket.create</methodName>
<params>
<param>
<value><string>{escape(summary)}</string></value>
</param>
<param>
<value><string>{escape(description)}</string></value>
</param>
<param>
<value><struct>
<member>
<name>component</name>
<value><string>{escape(component)}</string></value>
</member>
<member>
<name>priority</name>
<value><string>{escape(priority)}</string></value>
</member>
<member>
<name>keywords</name>
<value><string>{escape(keywords)}</string></value>
</member>
<member>
<name>author</name>
<value><string>gemini</string></value>
</member>
</struct></value>
</param>
<param>
<value><boolean>1</boolean></value>
</param>
</params>
</methodCall>
"""
    return xml_content

def send_to_trac(xml_content):
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
        
    xml_file_path = os.path.join(TEMP_DIR, "create_trac_ticket.xml")
    with open(xml_file_path, "w") as f:
        f.write(xml_content)

    curl_cmd = [
        "curl",
        "--silent",
        "--user", f"{TRAC_USER}:{TRAC_PASS}",
        "-H", "Content-Type: text/xml",
        "--data", f"@{xml_file_path}",
        TRAC_URL
    ]

    try:
        result = subprocess.run(curl_cmd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error sending to Trac: {e}")
        print(f"Stderr: {e.stderr}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Create Trac ticket from Vikunja task")
    parser.add_argument("task_id", type=int, help="Vikunja Task ID")
    parser.add_argument("--component", default="recreation", help="Trac component")
    parser.add_argument("--priority", default="major", help="Trac priority")
    parser.add_argument("--keywords", default="awp, crdo, Jen", help="Comma-separated keywords")
    parser.add_argument("--add-keywords", help="Additional keywords to append")

    args = parser.parse_args()

    # 1. Fetch Vikunja Task
    task = get_vikunja_task(args.task_id)
    print(f"Found Vikunja Task: {task.get('title')}")

    # 2. Prepare Trac Data
    summary = task.get('title')
    
    # Check for empty description
    vikunja_desc = task.get('description', '')
    vikunja_link = f"http://todo.gafla.us.com/tasks/{args.task_id}"
    
    description = f"Refers to Vikunja Task: {vikunja_link}\n\n{vikunja_desc}"
    
    keywords = args.keywords
    if args.add_keywords:
        keywords += f", {args.add_keywords}"

    # 3. Create XML Payload
    xml_payload = create_trac_ticket_xml(summary, description, args.component, args.priority, keywords)
    
    # 4. Send to Trac
    print("Creating Trac ticket...")
    response_xml = send_to_trac(xml_payload)
    
    # 5. Parse Response (Simple extraction)
    if "<int>" in response_xml:
        try:
            ticket_id = response_xml.split("<int>")[1].split("</int>")[0]
            print(f"Successfully created Trac Ticket #{ticket_id}")
            
            trac_public_url = f"{TRAC_PUBLIC_URL_BASE}/{ticket_id}"
            print(f"URL: {trac_public_url}")

            # 6. Update Vikunja Task
            print("Linking Trac ticket in Vikunja task...")
            
            # Avoid duplicating the link if it already exists
            if trac_public_url not in vikunja_desc:
                new_desc = vikunja_desc
                if new_desc:
                    new_desc += "<br><br>"
                new_desc += f'<a href="{trac_public_url}">Trac Ticket #{ticket_id}: {summary}</a>'
                
                update_vikunja_task(args.task_id, new_desc)
            else:
                print("Vikunja task already has this Trac ticket linked.")

        except IndexError:
            print("Ticket created but couldn't parse ID from response.")
            print(response_xml)
    else:
        print("Failed to create ticket. Response:")
        print(response_xml)

if __name__ == "__main__":
    main()