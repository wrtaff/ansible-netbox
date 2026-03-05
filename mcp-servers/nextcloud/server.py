#!/usr/bin/env python3
"""
================================================================================
Filename:       mcp-servers/nextcloud/server.py
Version:        1.3
Author:         Gemini CLI
Last Modified:  2026-03-05
Context:        http://trac.home.arpa/ticket/3154

Purpose:
    Model Context Protocol (MCP) server for Nextcloud integration.
    Provides tools for contact management (search, create, update, delete)
    directly within AI agent sessions.

Revision History:
    v1.3 (2026-03-05): Standardized VCard handling: added folding/unfolding,
                       proper property escaping, and unified NOTE handling.
    v1.2 (2026-03-05): Improved VCard handling: escaped/unescaped newlines;
                       combined multiple NOTE fields into a single display.
    v1.1 (2026-03-04): Updated header to WWOS standards; fixed syntax errors
                       in _construct_vcard and search_contacts.
    v1.0 (2026-03-04): Initial implementation with contact management tools.

Notes:
    Always bump the version number when modifying this file and annotate 
    the changes in the Revision History section.
================================================================================
"""
import os
import sys
import uuid
import logging
import requests
import subprocess
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Any
from collections import defaultdict
from mcp.server.fastmcp import FastMCP

# Configure logging to file
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='/tmp/nextcloud_mcp.log',
    filemode='a'
)
logger = logging.getLogger("nextcloud-mcp")

# Initialize FastMCP server
mcp = FastMCP("nextcloud-server")

def get_nextcloud_password():
    """Gets the NEXTCLOUD_PASSWORD, falling back to ~/.bashrc or vault if not set."""
    password = os.getenv("NEXTCLOUD_PASSWORD")
    if password:
        logger.info("NEXTCLOUD_PASSWORD found in environment.")
        return password

    # Try ~/.bashrc
    bashrc_path = os.path.expanduser("~/.bashrc")
    if os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "r") as f:
                for line in f:
                    if "export NEXTCLOUD_PASSWORD=" in line:
                        parts = line.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip('"').strip("'")
                            logger.info("NEXTCLOUD_PASSWORD found in ~/.bashrc.")
                            return val
        except Exception as e:
            logger.error(f"Error reading ~/.bashrc: {e}")

    # Try vault (via temp file cache first)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tmp_pass_file = os.path.join(script_dir, "..", "..", "tmp", "nextcloud_pass.txt")
    if os.path.exists(tmp_pass_file):
        try:
            with open(tmp_pass_file, 'r') as f:
                logger.info("NEXTCLOUD_PASSWORD found in temp cache.")
                return f.read().strip()
        except Exception:
            pass

    logger.warning("NEXTCLOUD_PASSWORD not found.")
    return None

# Nextcloud Configuration
DEFAULT_URL = "https://ynh2.van-bee.ts.net/nextcloud"
NEXTCLOUD_URL = os.getenv("NEXTCLOUD_URL", DEFAULT_URL).rstrip('/')
NEXTCLOUD_USER = os.getenv("NEXTCLOUD_USER", "will")
NEXTCLOUD_PASSWORD = get_nextcloud_password()

class NextcloudContactManager:
    def __init__(self, base_url, username, password, addressbook="contacts", verify=True):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.addressbook = addressbook
        self.verify = verify
        self.dav_url = f"{self.base_url}/remote.php/dav/addressbooks/users/{self.username}/{self.addressbook}/"
        self.session = requests.Session()
        self.session.auth = (self.username, self.password)
        self.session.headers.update({"Content-Type": "application/xml", "User-Agent": "GeminiCLI/MCP-1.0"})
        # Disable warnings if verify is False
        if not verify:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.verify = self.verify

    def list_contacts(self):
        body = """
        <d:propfind xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:carddav">
            <d:prop>
                <d:getetag />
                <c:address-data />
            </d:prop>
        </d:propfind>
        """
        try:
            response = self.session.request('PROPFIND', self.dav_url, data=body, headers={'Depth': '1'})
            if response.status_code == 207:
                return self._parse_multistatus(response.text)
            else:
                logger.error(f"Error fetching contacts: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return []

    def _parse_multistatus(self, xml_text):
        contacts = []
        try:
            namespaces = {'d': 'DAV:', 'c': 'urn:ietf:params:xml:ns:carddav'}
            root = ET.fromstring(xml_text)
            for response in root.findall('d:response', namespaces):
                href_elem = response.find('d:href', namespaces)
                if href_elem is None: continue
                href = href_elem.text
                propstat = response.find('d:propstat', namespaces)
                if propstat:
                    prop = propstat.find('d:prop', namespaces)
                    if prop:
                        address_data = prop.find('c:address-data', namespaces)
                        if address_data is not None and address_data.text:
                            vcard_text = address_data.text
                            contacts.append({
                                'href': href,
                                'fn': self._extract_field(vcard_text, 'FN'),
                                'emails': self._extract_fields(vcard_text, 'EMAIL'),
                                'tels': self._extract_fields(vcard_text, 'TEL'),
                                'categories': self._extract_field(vcard_text, 'CATEGORIES'),
                                'address': self._extract_field(vcard_text, 'ADR'),
                                'urls': self._extract_fields(vcard_text, 'URL'),
                                'note': "\n".join(self._extract_fields(vcard_text, 'NOTE')),
                                'org': self._extract_field(vcard_text, 'ORG'),
                                'title': self._extract_field(vcard_text, 'TITLE'),
                                'uid': self._extract_field(vcard_text, 'UID'),
                                'vcard': vcard_text
                            })
        except Exception as e:
            logger.error(f"Error parsing XML: {e}")
        return contacts

    def _extract_field(self, vcard, field_name):
        unfolded = self._unfold_vcard(vcard)
        for line in unfolded.splitlines():
            if line.startswith(field_name + ":") or line.startswith(field_name + ";"):
                parts = line.split(':', 1)
                val = parts[1] if len(parts) > 1 else ""
                return self._unescape_vcard_value(val)
        return ""

    def _extract_fields(self, vcard, field_name):
        values = []
        unfolded = self._unfold_vcard(vcard)
        for line in unfolded.splitlines():
            if line.startswith(field_name + ":") or line.startswith(field_name + ";"):
                parts = line.split(':', 1)
                if len(parts) > 1:
                    values.append(self._unescape_vcard_value(parts[1]))
        return values

    def _unfold_vcard(self, vcard_text):
        # Unfold: Join lines that start with space or tab
        lines = vcard_text.splitlines()
        if not lines: return ""
        unfolded = []
        for line in lines:
            if line.startswith((' ', '\t')) and unfolded:
                unfolded[-1] += line[1:]
            else:
                unfolded.append(line)
        return "\n".join(unfolded)

    def _fold_vcard_line(self, line):
        # Fold: Max 75 octets per line (simplified to chars here)
        if len(line) <= 75: return line
        folded = [line[:75]]
        for i in range(75, len(line), 74):
            folded.append(" " + line[i:i+74])
        return "\r\n".join(folded)

    def _escape_vcard_value(self, val):
        if not val: return ""
        return val.replace('\\', '\\\\').replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')

    def _unescape_vcard_value(self, val):
        if not val: return ""
        return val.replace('\\n', '\n').replace('\\N', '\n').replace('\\,', ',').replace('\\;', ';').replace('\\\\', '\\')

    def _construct_vcard(self, vcard_data):
        lines = ["BEGIN:VCARD"]
        version = vcard_data.pop('VERSION', ['3.0'])
        for ver in version:
            lines.append(f"VERSION:{ver}")
        for key, values in vcard_data.items():
            for val in values:
                val_esc = self._escape_vcard_value(val)
                line = f"{key}:{val_esc}"
                lines.append(self._fold_vcard_line(line))
        lines.append("END:VCARD")
        return "\r\n".join(lines)

    def _parse_vcard_lines(self, vcard_text):
        data = defaultdict(list)
        unfolded = self._unfold_vcard(vcard_text)
        for line in unfolded.splitlines():
            line = line.strip()
            if not line or line in ["BEGIN:VCARD", "END:VCARD"]: continue
            if ":" in line:
                key, value = line.split(":", 1)
                data[key].append(self._unescape_vcard_value(value))
        return data

    def search_contacts(self, query):
        all_contacts = self.list_contacts()
        query_lower = query.lower()
        return [c for c in all_contacts if c['fn'] and query_lower in c['vcard'].lower()]

    def create_contact(self, fn, email=None, tel=None, categories=None, address=None, url=None, note=None, org=None, title=None):
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
        if org: vcard_data['ORG'].append(org)
        if title: vcard_data['TITLE'].append(title)
        vcard_str = self._construct_vcard(vcard_data)
        resource_url = f"{self.dav_url}{uid}.vcf"
        try:
            response = self.session.put(resource_url, data=vcard_str.encode('utf-8'), headers={'Content-Type': 'text/vcard; charset=utf-8'})
            return response.status_code in [201, 204], uid
        except Exception as e:
            logger.error(f"Create failed: {e}")
            return False, str(e)

    def update_contact(self, uid, fn=None, email=None, tel=None, categories=None, address=None, url=None, note=None, org=None, title=None):
        contacts = self.list_contacts()
        href = next((c['href'] for c in contacts if c['uid'] == uid), None)
        if not href: return False, "UID not found"
        from urllib.parse import urlparse
        parsed_base = urlparse(self.base_url)
        vcf_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
        try:
            # 1. Fetch current VCard and ETag
            response = self.session.get(vcf_url)
            if response.status_code != 200: return False, f"Error fetching: {response.status_code}"
            etag = response.headers.get('ETag')
            vcard_data = self._parse_vcard_lines(response.text)
            
            # 2. Update fields
            if fn: vcard_data['FN'] = [fn]
            if email: self._append_if_missing(vcard_data, 'EMAIL;TYPE=INTERNET', email)
            if tel: self._append_if_missing(vcard_data, 'TEL;TYPE=HOME', tel)
            if categories: self._append_if_missing(vcard_data, 'CATEGORIES', categories)
            if url: self._append_if_missing(vcard_data, 'URL', url)
            
            if note:
                existing_notes = vcard_data.get('NOTE', [])
                # If note is not already a substring of the combined notes, add it
                combined = "\n".join(existing_notes)
                if note not in combined:
                    if existing_notes:
                        # Standardize on a single merged NOTE field
                        vcard_data['NOTE'] = [combined + "\n" + note]
                    else:
                        vcard_data['NOTE'] = [note]
                else:
                    # If it's already there, we might still want to consolidate if there are multiple fields
                    vcard_data['NOTE'] = [combined]

            if org: vcard_data['ORG'] = [org]
            if title: vcard_data['TITLE'] = [title]
            if address:
                exists = any(address in adr for adr in vcard_data.get('ADR;TYPE=HOME', []) + vcard_data.get('ADR', []))
                if not exists: vcard_data['ADR;TYPE=HOME'].append(f";;{address};;;;")
            
            # 3. Construct and PUT back
            vcard_str = self._construct_vcard(vcard_data)
            headers = {'Content-Type': 'text/vcard; charset=utf-8'}
            if etag: headers['If-Match'] = etag
            
            response = self.session.put(vcf_url, data=vcard_str.encode('utf-8'), headers=headers)
            if response.status_code in [200, 201, 204]:
                return True, ""
            else:
                logger.error(f"PUT failed: {response.status_code} - {response.text}")
                return False, f"PUT failed: {response.status_code} {response.reason}"
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return False, str(e)

    def _append_if_missing(self, data, key, value):
        if value not in data[key]: data[key].append(value)

    def delete_contact(self, uid):
        contacts = self.list_contacts()
        href = next((c['href'] for c in contacts if c['uid'] == uid), None)
        if not href: return False
        from urllib.parse import urlparse
        parsed_base = urlparse(self.base_url)
        vcf_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
        try:
            response = self.session.delete(vcf_url)
            return response.status_code in [200, 204]
        except Exception as e:
            logger.error(f"Delete failed: {e}")
            return False

def get_manager():
    if not NEXTCLOUD_PASSWORD:
        logger.error("Attempted to get manager without NEXTCLOUD_PASSWORD.")
        raise ValueError("NEXTCLOUD_PASSWORD is not set")
    # Defaulting to no verification if specified in env
    verify_env = os.getenv("NEXTCLOUD_VERIFY_SSL", "true").lower()
    verify = (verify_env == "true")
    return NextcloudContactManager(NEXTCLOUD_URL, NEXTCLOUD_USER, NEXTCLOUD_PASSWORD, verify=verify)

@mcp.tool(name="nextcloud_ping")
def ping() -> str:
    """A simple ping tool to verify MCP transport connectivity."""
    logger.info("Ping tool called.")
    return "pong"

@mcp.tool(name="nextcloud_search_contacts")
def search_contacts(query: str) -> str:
    """Search for contacts in Nextcloud. Matches against name, email, or any VCard field."""
    logger.info(f"Searching contacts with query: {query}")
    try:
        manager = get_manager()
        results = manager.search_contacts(query)
        if not results: return "No contacts found."
        output = []
        for c in results:
            # Format nicely
            emails = ", ".join(c['emails']) if c['emails'] else "N/A"
            tels = ", ".join(c['tels']) if c['tels'] else "N/A"
            details = (f"- {c['fn']} (UID: {c['uid']})\n"
                       f"  Email: {emails}\n"
                       f"  Tel: {tels}\n"
                       f"  Org: {c['org']}, Title: {c['title']}\n"
                       f"  Address: {c['address']}\n"
                       f"  Notes: {c['note']}")
            output.append(details)
        return "\n".join(output)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return f"Error searching contacts: {e}"

@mcp.tool(name="nextcloud_create_contact")
def create_contact(fn: str, email: Optional[str] = None, tel: Optional[str] = None, 
                   address: Optional[str] = None, url: Optional[str] = None, 
                   note: Optional[str] = None, org: Optional[str] = None, 
                   title: Optional[str] = None, categories: Optional[str] = None) -> str:
    """Create a new contact in Nextcloud."""
    logger.info(f"Creating contact: {fn}")
    try:
        manager = get_manager()
        success, uid = manager.create_contact(fn, email, tel, categories, address, url, note, org, title)
        return f"Successfully created contact: {fn} (UID: {uid})" if success else f"Failed to create contact: {uid}"
    except Exception as e:
        logger.error(f"Create tool failed: {e}")
        return f"Error creating contact: {e}"

@mcp.tool(name="nextcloud_update_contact")
def update_contact(uid: str, fn: Optional[str] = None, email: Optional[str] = None, 
                   tel: Optional[str] = None, address: Optional[str] = None, 
                   url: Optional[str] = None, note: Optional[str] = None, 
                   org: Optional[str] = None, title: Optional[str] = None, 
                   categories: Optional[str] = None) -> str:
    """Update an existing contact in Nextcloud by UID. Appends new values for multi-value fields (EMAIL, TEL, URL, ADR, CATEGORIES)."""
    logger.info(f"Updating contact: {uid}")
    try:
        manager = get_manager()
        success, err = manager.update_contact(uid, fn, email, tel, categories, address, url, note, org, title)
        return f"Successfully updated contact: {uid}" if success else f"Failed to update contact: {err}"
    except Exception as e:
        logger.error(f"Update tool failed: {e}")
        return f"Error updating contact: {e}"

@mcp.tool(name="nextcloud_delete_contact")
def delete_contact(uid: str) -> str:
    """Delete a contact in Nextcloud by UID."""
    logger.info(f"Deleting contact: {uid}")
    try:
        manager = get_manager()
        success = manager.delete_contact(uid)
        return f"Successfully deleted contact: {uid}" if success else f"Failed to delete contact: {uid}"
    except Exception as e:
        logger.error(f"Delete tool failed: {e}")
        return f"Error deleting contact: {e}"

if __name__ == "__main__":
    logger.info("Starting Nextcloud MCP server...")
    mcp.run()
