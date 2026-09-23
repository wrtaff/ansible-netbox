#!/usr/bin/env python3
"""
================================================================================
Filename:       normalize_trac_keywords.py
Version:        1.0
Author:         Gemini CLI
Context:        http://trac.gafla.us.com/ticket/4718
WWOS:           http://wwos.home.arpa/index.php/Autonomous_agent_skills

Purpose:
    Normalizes Trac ticket keywords to strict canonical TCKL format:
    - All lowercase alphanumeric tokens
    - Hyphens allowed, no other punctuation
    - Converts legacy acronyms, CamelCase, and sigils (@, <15, etc.)
    - Removes duplicates while preserving order
    - Defaults to dry-run mode unless --apply is passed
================================================================================
"""
import os
import re
import sys
import argparse
import xmlrpc.client

# Custom mappings for known non-standard tokens
CUSTOM_TOKEN_MAP = {
    "<15": "lessthan15",
    "@wakul": "wakul",
    "@WAKUL": "wakul",
    "@pdbshop": "pdbshop",
    "@fla": "fla",
    "c&p": "c-p",
    "c&m": "c-m",
    "PROV-P1": "prov-p1",
    "PROV-P2": "prov-p2",
    "PROV-P3": "prov-p3",
    "SysAdmin": "sysadmin",
    "NetBox": "netbox",
    "TrueNAS": "truenas",
    "UniFi": "unifi",
    "UniFI": "unifi",
    "Unifi": "unifi",
    "MediaWiki": "mediawiki",
    "Mediawiki": "mediawiki",
    "JavaScript": "javascript",
    "LibreOffice": "libreoffice",
    "DevSecOps": "devsecops",
    "NabuCasa": "nabucasa",
    "FarmOS": "farmos",
    "farmOS": "farmos",
    "MySQL": "mysql",
    "PulseAudio": "pulseaudio",
    "IoT": "iot",
    "IOT": "iot",
    "HiDPI": "hidpi",
    "InputLeap": "inputleap",
    "WillShare": "willshare",
    "GuestBath": "guest-bath",
    "MasterBath": "master-bath",
    "GuestBedroom": "guest-bedroom",
    "PowderRoom": "powder-room",
    "CraftCloset": "craft-closet",
    "Laundryroom": "laundry-room",
    "Livingroom": "living-room",
    "ColdStorage": "cold-storage",
    "DataManagement": "data-management",
    "BuildFromSource": "build-from-source",
    "NUT-Client": "nut-client",
    "WLED-Controller": "wled-controller",
    "Gravity-Sync": "gravity-sync",
    "Google-Maps": "google-maps",
    "FCAPS-CONF": "fcaps-conf",
    "Bare-Metal": "bare-metal",
    "Limbo-f0": "limbo-f0",
    "Limbo-bd": "limbo-bd",
    "ToshLaptop": "tosh-laptop",
    "ForMama": "for-mama",
    "FunTasks": "fun-tasks",
    "HpP2055dn": "hpp2055dn",
    "iphoneXR-w": "iphonexr-w",
    "transcribe_audio": "transcribe-audio",
    "agent_api_token": "agent-api-token",
    "bootstrap.yml": "bootstrap-yml",
    "cli_help": "cli-help",
    "gemini_cli": "gemini-cli",
    "API_Error": "api-error",
    "google_assistant": "google-assistant",
    "Google_Drive": "google-drive",
    "home.arpa": "home-arpa",
    "libertypbc.org": "libertypbc.org",
    ".libertypbc.org": "libertypbc.org",
    "matrix.org": "matrix-org",
    "id.me": "id-me",
    "pay.gov": "pay-gov",
    "tsa.gov": "tsa-gov",
    "gCal": "gcal",
    "gDocs": "gdocs",
    "gSheets": "gsheets",
    "bFinance": "bfinance",
    "bHVAC": "bhvac",
    "bStructural": "bstructural",
    "Pi-hole": "pihole",
    "Pihole": "pihole",
}

def get_trac_password():
    """Gets the TRAC_PASSWORD, falling back to ~/.bashrc if not set in environment."""
    password = os.getenv("TRAC_PASSWORD")
    if password:
        return password

    bashrc_path = os.path.expanduser("~/.bashrc")
    if os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "r") as f:
                for line in f:
                    if (m := re.search(r'export TRAC_PASSWORD=[\'"]?([^\'"]+)[\'"]?', line)):
                        return m.group(1)
        except Exception:
            pass
    return None

def normalize_single_token(tok: str) -> str:
    """Normalizes a single keyword token to lowercase hyphenated format."""
    tok = tok.strip()
    if not tok:
        return ""
    
    # Check explicit custom map first
    if tok in CUSTOM_TOKEN_MAP:
        return CUSTOM_TOKEN_MAP[tok]
    
    # Strip leading/trailing punctuation like @ or commas
    tok = tok.lstrip("@").rstrip(",")
    if not tok:
        return ""

    if tok in CUSTOM_TOKEN_MAP:
        return CUSTOM_TOKEN_MAP[tok]

    # Convert camelCase / PascalCase to kebab-case if mixed case and no existing hyphen
    if re.search(r'[a-z][A-Z]', tok) and not tok.startswith("http"):
        tok = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', tok)

    # Convert underscores to hyphens
    tok = tok.replace('_', '-')

    # Lowercase everything
    tok = tok.lower()

    # Clean any non [a-z0-9.-]
    tok = re.sub(r'[^a-z0-9.-]', '', tok)
    tok = tok.strip('.-')

    return tok

def normalize_keywords_string(kws_str: str) -> str:
    """Parses a full keywords string, normalizes tokens, deduplicates, and returns space-separated."""
    if not kws_str:
        return ""
    
    # Split by whitespace and commas
    raw_tokens = re.split(r'[\s,]+', kws_str.strip())
    seen = set()
    norm_tokens = []

    for raw in raw_tokens:
        clean = normalize_single_token(raw)
        if clean and clean not in seen:
            seen.add(clean)
            norm_tokens.append(clean)

    return ' '.join(norm_tokens)

def main():
    parser = argparse.ArgumentParser(description="Normalize Trac keywords to canonical TCKL lowercase format.")
    parser.add_argument("--query", default="status!=closed", help="Trac query filter (default: 'status!=closed')")
    parser.add_argument("--apply", action="store_true", help="Apply updates live (default is dry-run)")
    parser.add_argument("--limit", type=int, default=0, help="Max tickets to process (0 = all)")
    args = parser.parse_args()

    password = get_trac_password()
    user = os.getenv("TRAC_USER", "will")
    host = os.getenv("TRAC_HOST", "trac.gafla.us.com")
    path = os.getenv("TRAC_PATH", "/login/xmlrpc")

    if not password:
        print("Error: TRAC_PASSWORD not found.")
        sys.exit(1)

    url = f"http://{user}:{password}@{host}{path}"
    server = xmlrpc.client.ServerProxy(url)

    print(f"Connecting to Trac ({host})...")
    ticket_ids = server.ticket.query(f"{args.query}&max=0")
    print(f"Found {len(ticket_ids)} tickets matching query: '{args.query}'")

    if args.limit > 0:
        ticket_ids = ticket_ids[:args.limit]
        print(f"Limited processing to {len(ticket_ids)} tickets.")

    mode_str = "LIVE APPLY" if args.apply else "DRY-RUN (no changes made)"
    print(f"Execution mode: {mode_str}\n")

    changes = []
    
    for i, tid in enumerate(ticket_ids, 1):
        try:
            t = server.ticket.get(tid)
            fields = t[3]
            old_kws = fields.get("keywords", "")
            new_kws = normalize_keywords_string(old_kws)

            if old_kws != new_kws:
                changes.append((tid, old_kws, new_kws, fields.get("summary", "")))
                print(f"[#{tid}] {fields.get('summary', '')[:50]}")
                print(f"   OLD: '{old_kws}'")
                print(f"   NEW: '{new_kws}'")

                if args.apply:
                    # Update keywords only
                    server.ticket.update(tid, "", {"keywords": new_kws}, False, "gemini")
                    print("   -> Updated successfully.")
        except Exception as e:
            print(f"Error on ticket #{tid}: {e}")

    print(f"\n==========================================")
    print(f"Total tickets evaluated: {len(ticket_ids)}")
    print(f"Total tickets with keyword changes: {len(changes)}")
    if not args.apply and len(changes) > 0:
        print(f"Run with --apply to execute these changes.")

if __name__ == "__main__":
    main()
