#!/usr/bin/env python3
"""
================================================================================
Filename:       manage_nextcloud_contacts.py
Version:        1.6
Author:         Gemini CLI
Last Modified:  2026-02-05
Context:        Nextcloud Contact Management Interface

Purpose:
    A CLI tool to interact with Nextcloud Contacts via CardDAV.
    Allows creating, retrieving, and updating contacts for the user.
    Version 1.4 supports appending values to multi-value fields (EMAIL, TEL, URL, ADR, CATEGORIES).
    Version 1.5 adds the ability to update a contact from a raw VCard file.
    Version 1.6 adds password caching to avoid repeated vault prompts.

Usage:
    # List all contacts
    ./manage_nextcloud_contacts.py list

    # Search for a contact
    ./manage_nextcloud_contacts.py search "John Doe"

    # Create a new contact
    ./manage_nextcloud_contacts.py create --fn "Jane Doe" --email "jane@example.com" --tel "555-0199" --address "123 Main St" --url "https://jane.com"

    # Update a contact (uid required) - Appends new values
    ./manage_nextcloud_contacts.py update <UID> --email "new@example.com" --url "https://newsite.com"

    # Update a contact from a VCard file
    ./manage_nextcloud_contacts.py update <UID> --vcard-file /path/to/contact.vcf

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
import subprocess
from collections import defaultdict

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
        self.dav_url = f"{self.base_url}/remote.php/dav/addressbooks/users/{self.username}/{self.addressbook}/"
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.headers.update({"Content-Type": "application/xml", "User-Agent": "GeminiCLI/1.5"})
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

    def create_contact(self, fn, email=None, tel=None, categories=None, address=None, url=None, note=None):
        """Creates a new contact using a VCard 3.0 template."""
        uid = str(uuid.uuid4())
        vcard_data = defaultdict(list)
        vcard_data['VERSION'].append("3.0")
        vcard_data['FN'].append(fn)
        vcard_data['N'].append(f"{fn};;;;")
        vcard_data['UID'].append(uid)
        
        if email: vcard_data['EMAIL;TYPE=WORK'].append(email)
        if tel: vcard_data['TEL;TYPE=CELL'].append(tel)
        if categories: vcard_data['CATEGORIES'].append(categories)
        if address: vcard_data['ADR;TYPE=HOME'].append(f";;{address};;;;")
        if url: vcard_data['URL'].append(url)
        if note: vcard_data['NOTE'].append(note)

        vcard_str = self._construct_vcard(vcard_data)
        resource_url = f"{self.dav_url}{uid}.vcf"
        
        response = self.session.put(resource_url, data=vcard_str, headers={'Content-Type': 'text/vcard; charset=utf-8'})
        
        if response.status_code in [201, 204]:
            print(f"Successfully created contact: {fn} (UID: {uid})")
            return True
        else:
            print(f"Error creating contact: {response.status_code} - {response.text}", file=sys.stderr)
            return False

    def get_contact_href_by_uid(self, uid):
        """Finds the HREF for a contact given its UID."""
        contacts = self.list_contacts()
        for contact in contacts:
            if contact['uid'] == uid:
                return contact['href']
        return None

    def update_contact(self, uid, fn=None, email=None, tel=None, categories=None, address=None, url=None, note=None, vcard_file=None):
        """
        Updates an existing contact. Fetches current VCard, parses to list, appends new values,
        or updates from a raw VCard file.
        """
        href = self.get_contact_href_by_uid(uid)
        if not href:
            print(f"Error: Contact with UID {uid} not found.")
            return False
            
        from urllib.parse import urlparse
        parsed_base = urlparse(self.base_url)
        vcf_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"

        if vcard_file:
            try:
                with open(vcard_file, 'r') as f:
                    vcard_str = f.read()
                response = self.session.put(vcf_url, data=vcard_str.encode('utf-8'), headers={'Content-Type': 'text/vcard; charset=utf-8'})
            except IOError as e:
                print(f"Error reading VCard file: {e}", file=sys.stderr)
                return False
        else:
            # 1. Fetch existing VCard
            response = self.session.get(vcf_url)
            if response.status_code != 200:
                print(f"Error fetching existing contact {uid}: {response.status_code}")
                return False
                
            # 2. Parse into Multi-Value Dict
            vcard_data = self._parse_vcard_lines(response.text)

            # 3. Update fields (Append if not exists, replace if single-value like FN)
            if fn: 
                vcard_data['FN'] = [fn] # Replace Name
                # Optional: Update N field smarter? Keeping it simple.

            if email: self._append_if_missing(vcard_data, 'EMAIL;TYPE=INTERNET', email)
            if tel: self._append_if_missing(vcard_data, 'TEL;TYPE=HOME', tel)
            if categories: self._append_if_missing(vcard_data, 'CATEGORIES', categories)
            if url: self._append_if_missing(vcard_data, 'URL', url)
            if note: self._append_if_missing(vcard_data, 'NOTE', note)
            
            if address:
                # Check if this address string is already in any ADR field
                # ADR format in vcard_data list is full string (e.g. ";;Street;;;;")
                # We want to match loosely on the street part
                exists = False
                for adr_line in vcard_data.get('ADR;TYPE=HOME', []) + vcard_data.get('ADR', []):
                    if address in adr_line:
                        exists = True
                        break
                if not exists:
                    vcard_data['ADR;TYPE=HOME'].append(f";;{address};;;;")

            # 4. Construct and Upload
            vcard_str = self._construct_vcard(vcard_data)
            response = self.session.put(vcf_url, data=vcard_str.encode('utf-8'))
        
        if response.status_code in [200, 201, 204]:
            return True
        else:
            print(f"Error updating contact: {response.status_code} - {response.text}")
            return False

    def delete_contact(self, uid):
        """Deletes a contact by UID."""
        href = self.get_contact_href_by_uid(uid)
        if not href:
            print(f"Error: Contact with UID {uid} not found.")
            return False

        from urllib.parse import urlparse
        parsed_base = urlparse(self.base_url)
        vcf_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"

        response = self.session.delete(vcf_url)
        
        if response.status_code in [200, 204]:
            print(f"Successfully deleted contact: {uid}")
            return True
        else:
            print(f"Error deleting contact: {response.status_code} - {response.text}", file=sys.stderr)
            return False

    def _parse_vcard_lines(self, vcard_text):
        """Parses VCard text into a dict of lists."""
        data = defaultdict(list)
        for line in vcard_text.splitlines():
            line = line.strip()
            if not line or line == "BEGIN:VCARD" or line == "END:VCARD":
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                data[key].append(value)
        return data

    def _construct_vcard(self, vcard_data):
        """Rebuilds VCard string from dict of lists."""
        lines = ["BEGIN:VCARD"]
        # Ensure VERSION is first
        for ver in vcard_data.pop('VERSION', ['3.0']):
            lines.append(f"VERSION:{ver}")
        
        for key, values in vcard_data.items():
            for val in values:
                lines.append(f"{key}:{val}")
        
        lines.append("END:VCARD")
        return "\r\n".join(lines)

    def _append_if_missing(self, data, key, value):
        """Appends value to data[key] if not already present."""
        if value not in data[key]:
            data[key].append(value)

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
                            # EMAIL, TEL, URL can be multiple
                            emails = self._extract_fields(vcard_text, 'EMAIL')
                            tels = self._extract_fields(vcard_text, 'TEL')
                            urls = self._extract_fields(vcard_text, 'URL')
                            categories = self._extract_field(vcard_text, 'CATEGORIES')
                            note = self._extract_field(vcard_text, 'NOTE')
                            
                            # Address usually one, but could be multiple.
                            # For display summary, just take the first one or clean it up.
                            address = self._extract_field(vcard_text, 'ADR')
                            if address.startswith(";;"):
                                parts = address.split(";")
                                if len(parts) > 2:
                                    address = parts[2]
                            
                            uid = self._extract_field(vcard_text, 'UID')
                            
                            contacts.append({
                                'href': href,
                                'fn': fn,
                                'emails': emails,
                                'tels': tels,
                                'categories': categories,
                                'address': address,
                                'urls': urls,
                                'note': note,
                                'uid': uid,
                                'vcard': vcard_text
                            })
        except Exception as e:
            print(f"Error parsing XML: {e}", file=sys.stderr)
        
        return contacts

    def _extract_field(self, vcard, field_name):
        """Simple text extraction for single-value VCard fields (first match)."""
        for line in vcard.splitlines():
            if line.startswith(field_name + ":") or line.startswith(field_name + ";"):
                parts = line.split(':', 1)
                if len(parts) > 1:
                    return parts[1]
        return ""

    def _extract_fields(self, vcard, field_name):
        """Extraction for multi-value VCard fields."""
        values = []
        for line in vcard.splitlines():
            if line.startswith(field_name + ":") or line.startswith(field_name + ";"):
                parts = line.split(':', 1)
                if len(parts) > 1:
                    values.append(parts[1])
        return values

def get_password_from_tmp():
    """Attempts to retrieve the nextcloud_user_will_pass from a temporary file."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tmp_pass_file = os.path.join(script_dir, "..", "tmp", "nextcloud_pass.txt")
    
    if os.path.exists(tmp_pass_file):
        try:
            with open(tmp_pass_file, 'r') as f:
                return f.read().strip()
        except Exception:
            pass
    return None

def get_password_from_vault(ask_vault_pass=False):
    """Attempts to retrieve the nextcloud_user_will_pass from vault.yml using ansible-vault."""
    # Check cache first
    cached_pass = get_password_from_tmp()
    if cached_pass:
        return cached_pass

    script_dir = os.path.dirname(os.path.abspath(__file__))
    vault_file = os.path.join(script_dir, "..", "vault.yml")
    
    if not os.path.exists(vault_file):
        print(f"DEBUG: Vault file not found at {vault_file}", file=sys.stderr)
        return None
    
    cmd = ["ansible-vault", "view", vault_file]
    if ask_vault_pass:
        cmd.append("--ask-vault-pass")
        
    try:
        # If ask_vault_pass is True, this will prompt the user in the terminal
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        for line in result.stdout.splitlines():
            if "nextcloud_user_will_pass:" in line:
                # Extract value after the colon and strip quotes
                token = line.split(":", 1)[1].strip().strip("'").strip('"')
                
                # Cache it
                if token:
                    tmp_pass_file = os.path.join(script_dir, "..", "tmp", "nextcloud_pass.txt")
                    try:
                        os.makedirs(os.path.dirname(tmp_pass_file), exist_ok=True)
                        with open(tmp_pass_file, 'w') as f:
                            f.write(token)
                        os.chmod(tmp_pass_file, 0o600)
                    except Exception as e:
                        print(f"DEBUG: Could not save temp password: {e}", file=sys.stderr)
                
                return token
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        # If we failed but didn't ask for pass, maybe we should have?
        # But for now, just pass.
        pass
    return None

def main():
    parser = argparse.ArgumentParser(description="Manage Nextcloud Contacts")
    parser.add_argument("--no-verify", action="store_false", dest="verify", help="Disable SSL certificate verification")
    parser.add_argument("--ask-vault-pass", action="store_true", help="Ask for vault password to retrieve Nextcloud password")
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
    create_parser.add_argument("--address", help="Home Street Address")
    create_parser.add_argument("--url", help="Website URL")
    create_parser.add_argument("--note", help="Notes")

    # Update Command
    update_parser = subparsers.add_parser("update", help="Update an existing contact")
    update_parser.add_argument("uid", help="UID of the contact to update")
    update_parser.add_argument("--fn", help="Full Name")
    update_parser.add_argument("--email", help="Email address")
    update_parser.add_argument("--tel", help="Telephone number")
    update_parser.add_argument("--categories", help="Comma-separated categories/labels")
    update_parser.add_argument("--address", help="Home Street Address")
    update_parser.add_argument("--url", help="Website URL")
    update_parser.add_argument("--note", help="Notes")
    update_parser.add_argument("--vcard-file", help="Path to a VCard file for updating")

    # Delete Command
    delete_parser = subparsers.add_parser("delete", help="Delete a contact")
    delete_parser.add_argument("uid", help="UID of the contact to delete")

    args = parser.parse_args()

    # Environment Setup
    url = os.getenv("NEXTCLOUD_URL", DEFAULT_URL)
    user = os.getenv("NEXTCLOUD_USER", DEFAULT_USER)
    password = os.getenv("NEXTCLOUD_PASSWORD")
    
    if not password:
        password = get_password_from_vault(args.ask_vault_pass)

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
                addr = f" [Addr: {c['address']}]" if c['address'] else ""
                urls = f" [URLs: {', '.join(c['urls'])}]" if c['urls'] else ""
                note = f" [Note: {c['note']}]" if c['note'] else ""
                # Join first email/tel for brevity if list
                email_display = c['emails'][0] if c['emails'] else ""
                tel_display = c['tels'][0] if c['tels'] else ""
                
                print(f"- {c['fn']} ({email_display}) [Tel: {tel_display}]{cats}{addr}{urls}{note} [UID: {c['uid']}] [HREF: {c['href']}]")

    elif args.command == "search":
        results = manager.search_contacts(args.query)
        print(f"Found {len(results)} matches:")
        for c in results:
             if c['fn']:
                cats = f" [Cats: {c['categories']}]" if c['categories'] else ""
                addr = f" [Addr: {c['address']}]" if c['address'] else ""
                urls = f" [URLs: {', '.join(c['urls'])}]" if c['urls'] else ""
                note = f" [Note: {c['note']}]" if c['note'] else ""
                email_display = c['emails'][0] if c['emails'] else ""
                tel_display = c['tels'][0] if c['tels'] else ""

                print(f"- {c['fn']} ({email_display}) [Tel: {tel_display}]{cats}{addr}{urls}{note} [UID: {c['uid']}] [HREF: {c['href']}]")

    elif args.command == "create":
        manager.create_contact(args.fn, args.email, args.tel, args.categories, args.address, args.url, args.note)

    elif args.command == "update":
        if manager.update_contact(args.uid, args.fn, args.email, args.tel, args.categories, args.address, args.url, args.note, args.vcard_file):
            print(f"Successfully updated contact: {args.uid}")

    elif args.command == "delete":
        manager.delete_contact(args.uid)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
