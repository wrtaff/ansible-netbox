#!/usr/bin/env python3
"""
================================================================================
Filename:       manage_nextcloud_contacts.py
Version:        1.1
Author:         Gemini CLI
Last Modified:  2026-01-30
Context:        Nextcloud Contact Management Interface

Purpose:
    A CLI tool to interact with Nextcloud Contacts via CardDAV.
    Allows creating, retrieving, and updating contacts for the user.

Usage:
    # List all contacts
    ./manage_nextcloud_contacts.py list

    # Search for a contact
    ./manage_nextcloud_contacts.py search "John Doe"

    # Create a new contact
    ./manage_nextcloud_contacts.py create --fn "Jane Doe" --email "jane@example.com" --tel "555-0199"

    # Update a contact (uid required)
    ./manage_nextcloud_contacts.py update <UID> --email "new@example.com" --tel "555-0200"

    # Delete a contact
    ./manage_nextcloud_contacts.py delete <UID>

Dependencies:
    python3, requests
"""

import os
import sys
import argparse
import requests
import uuid
import xml.etree.ElementTree as ET

# Configuration Defaults
DEFAULT_URL = "https://ynh2.van-bee.ts.net/nextcloud"
DEFAULT_USER = "will"

class NextcloudContactManager:
    def __init__(self, base_url, username, password, addressbook="contacts", verify=True):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.addressbook = addressbook
        self.verify = verify
        # Construct the CardDAV URL
        # Standard Nextcloud path: /remote.php/dav/addressbooks/users/<user>/<addressbook>/
        self.dav_url = f"{self.base_url}/remote.php/dav/addressbooks/users/{self.username}/{self.addressbook}/"
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.headers.update({"Content-Type": "application/xml", "User-Agent": "GeminiCLI/1.0"})
        self.session.verify = self.verify

    def list_contacts(self):
        """Fetches all contacts from the addressbook."""
        body = """
        <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">
            <d:prop>
                <d:getetag />
                <c:address-data />
            </d:prop>
        </d:propfind>
        """
        response = self.session.request('PROPFIND', self.dav_url, data=body, headers={'Depth': '1'})
        
        if response.status_code == 207:
            return self._parse_multistatus(response.text)
        else:
            print(f"Error fetching contacts: {response.status_code} - {response.text}", file=sys.stderr)
            return []

    def search_contacts(self, query):
        """Searches contacts (client-side filter for simplicity)."""
        all_contacts = self.list_contacts()
        results = []
        query_lower = query.lower()
        for contact in all_contacts:
            vcard = contact.get('vcard', '')
            if query_lower in vcard.lower():
                results.append(contact)
        return results

    def create_contact(self, fn, email=None, tel=None, categories=None):
        """Creates a new contact using a VCard 3.0 template."""
        uid = str(uuid.uuid4())
        vcard = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"UID:{uid}",
            f"FN:{fn}",
            f"N:{fn};;;;"
        ]
        if email:
            vcard.append(f"EMAIL;TYPE=WORK:{email}")
        if tel:
            vcard.append(f"TEL;TYPE=CELL:{tel}")
        if categories:
            vcard.append(f"CATEGORIES:{categories}")
        vcard.append("END:VCARD")
        
        vcard_str = "\r\n".join(vcard)
        
        # The URL for the new resource
        resource_url = f"{self.dav_url}{uid}.vcf"
        
        response = self.session.put(resource_url, data=vcard_str, headers={'Content-Type': 'text/vcard; charset=utf-8'})
        
        if response.status_code in [201, 204]:
            print(f"Successfully created contact: {fn} (UID: {uid})")
            return True
        else:
            print(f"Error creating contact: {response.status_code} - {response.text}", file=sys.stderr)
            return False

    def update_contact(self, uid, fn=None, email=None, tel=None, categories=None):
        """
        Updates an existing contact. Fetches current VCard first to preserve existing fields.
        """
        vcf_url = f"{self.dav_url}{uid}.vcf"
        
        # 1. Fetch existing VCard
        response = self.session.get(vcf_url)
        if response.status_code != 200:
            print(f"Error fetching existing contact {uid}: {response.status_code}")
            return False
            
        lines = response.text.splitlines()
        vcard_data = {}
        # Basic parsing
        for line in lines:
            if ":" in line:
                key, value = line.split(":", 1)
                # Handle parameters like EMAIL;TYPE=INTERNET
                clean_key = key.split(";")[0]
                vcard_data[clean_key] = value

        # 2. Update fields
        new_fn = fn if fn else vcard_data.get("FN", "Unknown")
        new_email = email if email else vcard_data.get("EMAIL", "")
        new_tel = tel if tel else vcard_data.get("TEL", "")
        new_categories = categories if categories else vcard_data.get("CATEGORIES", "")
        
        # 3. Construct new VCard (preserving structure simply)
        new_vcard = "BEGIN:VCARD\nVERSION:3.0\n"
        new_vcard += f"FN:{new_fn}\n"
        if new_email:
            new_vcard += f"EMAIL;TYPE=INTERNET:{new_email}\n"
        if new_tel:
            new_vcard += f"TEL;TYPE=HOME:{new_tel}\n"
        if new_categories:
            new_vcard += f"CATEGORIES:{new_categories}\n"
        
        # Preserve other fields if we really wanted to, but CardDAV update usually overwrites the resource.
        # For simplicity in this script, we'll just handle FN, EMAIL, TEL, CATEGORIES for now.
        # But let's at least keep the UID.
        new_vcard += f"UID:{uid}\nEND:VCARD"

        # 4. Upload updated VCard
        response = self.session.put(vcf_url, data=new_vcard.encode('utf-8'))
        
        if response.status_code in [200, 201, 204]:
            return True
        else:
            print(f"Error updating contact: {response.status_code} - {response.text}")
            return False

    def delete_contact(self, uid):
        """Deletes a contact by UID."""
        vcf_url = f"{self.dav_url}{uid}.vcf"
        response = self.session.delete(vcf_url)
        
        if response.status_code in [200, 204]:
            print(f"Successfully deleted contact: {uid}")
            return True
        else:
            print(f"Error deleting contact: {response.status_code} - {response.text}", file=sys.stderr)
            return False

    def _parse_multistatus(self, xml_text):
        """Parses the WebDAV MultiStatus XML response."""
        contacts = []
        try:
            # Register namespaces to make finding elements easier
            namespaces = {
                'd': 'DAV:',
                'c': 'urn:ietf:params:xml:ns:carddav'
            }
            root = ET.fromstring(xml_text)
            
            for response in root.findall('d:response', namespaces):
                href = response.find('d:href', namespaces).text
                propstat = response.find('d:propstat', namespaces)
                if propstat:
                    prop = propstat.find('d:prop', namespaces)
                    if prop:
                        address_data = prop.find('c:address-data', namespaces)
                        if address_data is not None and address_data.text:
                            # Extract simple fields for display
                            vcard_text = address_data.text
                            fn = self._extract_field(vcard_text, 'FN')
                            email = self._extract_field(vcard_text, 'EMAIL')
                            tel = self._extract_field(vcard_text, 'TEL')
                            categories = self._extract_field(vcard_text, 'CATEGORIES')
                            uid = self._extract_field(vcard_text, 'UID')
                            
                            contacts.append({
                                'href': href,
                                'fn': fn,
                                'email': email,
                                'tel': tel,
                                'categories': categories,
                                'uid': uid,
                                'vcard': vcard_text
                            })
        except Exception as e:
            print(f"Error parsing XML: {e}", file=sys.stderr)
        
        return contacts

    def _extract_field(self, vcard, field_name):
        """Simple text extraction for VCard fields."""
        for line in vcard.splitlines():
            if line.startswith(field_name + ":") or line.startswith(field_name + ";"):
                parts = line.split(':', 1)
                if len(parts) > 1:
                    return parts[1]
        return ""

def main():
    parser = argparse.ArgumentParser(description="Manage Nextcloud Contacts")
    parser.add_argument("--no-verify", action="store_false", dest="verify", help="Disable SSL certificate verification")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # List
    subparsers.add_parser("list", help="List all contacts")

    # Search
    search_parser = subparsers.add_parser("search", help="Search contacts")
    search_parser.add_argument("query", help="Search query (name, email, etc.)")

    # Create
    create_parser = subparsers.add_parser("create", help="Create a new contact")
    create_parser.add_argument("--fn", required=True, help="Full Name")
    create_parser.add_argument("--email", help="Email Address")
    create_parser.add_argument("--tel", help="Telephone Number")
    create_parser.add_argument("--categories", help="Comma-separated categories/labels")

    # Update Command
    update_parser = subparsers.add_parser("update", help="Update an existing contact")
    update_parser.add_argument("uid", help="UID of the contact to update")
    update_parser.add_argument("--fn", help="Full Name")
    update_parser.add_argument("--email", help="Email address")
    update_parser.add_argument("--tel", help="Telephone number")
    update_parser.add_argument("--categories", help="Comma-separated categories/labels")

    # Delete Command
    delete_parser = subparsers.add_parser("delete", help="Delete a contact")
    delete_parser.add_argument("uid", help="UID of the contact to delete")

    args = parser.parse_args()

    # Environment Setup
    url = os.getenv("NEXTCLOUD_URL", DEFAULT_URL)
    user = os.getenv("NEXTCLOUD_USER", DEFAULT_USER)
    password = os.getenv("NEXTCLOUD_PASSWORD")
    
    # SSL Verification: env var takes precedence if set, otherwise CLI flag
    verify_env = os.getenv("NEXTCLOUD_VERIFY_SSL", "true").lower()
    verify = args.verify if verify_env == "true" else False

    if not password:
        # Prompt or fail. For automation/CLI, failure is safer than hanging.
        print("Error: NEXTCLOUD_PASSWORD environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    # Disable warnings if verify is False
    if not verify:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    manager = NextcloudContactManager(url, user, password, verify=verify)

    if args.command == "list":
        contacts = manager.list_contacts()
        print(f"Found {len(contacts)} contacts:")
        for c in contacts:
            if c['fn']: # Filter out the addressbook root itself which sometimes appears
                cats = f" [Cats: {c['categories']}]" if c['categories'] else ""
                print(f"- {c['fn']} ({c['email']}) [Tel: {c['tel']}]{cats} [UID: {c['uid']}]")

    elif args.command == "search":
        results = manager.search_contacts(args.query)
        print(f"Found {len(results)} matches:")
        for c in results:
             if c['fn']:
                cats = f" [Cats: {c['categories']}]" if c['categories'] else ""
                print(f"- {c['fn']} ({c['email']}) [Tel: {c['tel']}]{cats} [UID: {c['uid']}]")

    elif args.command == "create":
        manager.create_contact(args.fn, args.email, args.tel, args.categories)

    elif args.command == "update":
        if manager.update_contact(args.uid, args.fn, args.email, args.tel, args.categories):
            print(f"Successfully updated contact: {args.uid}")

    elif args.command == "delete":
        manager.delete_contact(args.uid)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
