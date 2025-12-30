#!/usr/bin/env python3
"""
Github Safety Scanner
=====================
Scans directories for potential hardcoded secrets (passwords, keys, tokens)
to prevent accidental commits to public repositories.

Usage:
    ./github_safety_scan.py [directory_to_scan]

Default directories: scripts, playbooks
"""

import os
import re
import sys
import argparse

# Configuration
DEFAULT_DIRS = ["scripts", "playbooks"]
IGNORE_EXTENSIONS = [".pyc", ".zip", ".tar", ".gz", ".log", ".retry", ".swp"]
IGNORE_FILES = ["vault.yml"] # Encrypted files

# Regex patterns for finding potential secrets
# captured group 'secret' is the value to check
PATTERNS = [
    # Assignment: var = "secret" or var: "secret"
    # Looks for key words like password, secret, token, api_key followed by assignment
    re.compile(r"""(?i)(?P<key>password|passwd|secret|token|api_key|access_key|auth_key)[\s]*[:=][\s]*["'](?P<value>[^'"\s]+)["']"""),
    
    # URLs with credentials: http://user:pass@host
    re.compile(r'://[^:]+:(?P<value>[^@]+)@'),
    
    # Specific keys (like RSA private blocks) - basic check
    re.compile(r'(?P<value>-----BEGIN [A-Z]+ PRIVATE KEY-----)'),
]

# Whitelist values that are false positives
WHITELIST = [
    "!!CHANGE_ME_PLEASE!!",
    "your_password",
    "your_username",
    "root",
    "admin",
    "password",
    "secret",
    "{{ ",  # Ansible variables
    "{% ",  # Jinja2
    "os.getenv",
    "os.environ",
    "lookup(",
]

def is_suspicious(value):
    """
    Determines if a value looks like a real secret.
    """
    if not value or len(value) < 3:
        return False
    
    # Check whitelist
    for safe_val in WHITELIST:
        if safe_val in value:
            return False
            
    # Heuristic: variable references often look like {{ var }} or $VAR
    if value.startswith("{{") or value.startswith("${ "):
        return False
        
    return True

def scan_file(filepath):
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines):
            line_num = i + 1
            line = line.strip()
            
            # Skip comments (basic check)
            if line.startswith("#") or line.startswith("//"):
                continue

            for pattern in PATTERNS:
                match = pattern.search(line)
                if match:
                    # Determine value based on regex group name
                    if 'value' in match.groupdict():
                        val = match.group('value')
                        
                        if is_suspicious(val):
                            issues.append({
                                "line": line_num,
                                "content": line,
                                "match": val
                            })
                            # Break inner loop to avoid double reporting same line
                            break
                            
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        
    return issues

def main():
    parser = argparse.ArgumentParser(description="Scan files for hardcoded secrets.")
    parser.add_argument("dirs", nargs="*", help="Directories to scan", default=DEFAULT_DIRS)
    args = parser.parse_args()

    # Normalize directories
    dirs_to_scan = [d for d in args.dirs if os.path.exists(d)]
    
    if not dirs_to_scan:
        print("No valid directories found to scan.")
        sys.exit(1)

    print(f"Scanning directories: {', '.join(dirs_to_scan)}...")
    print("-" * 60)

    found_secrets = False

    for directory in dirs_to_scan:
        for root, _, files in os.walk(directory):
            for filename in files:
                if filename in IGNORE_FILES:
                    continue
                    
                _, ext = os.path.splitext(filename)
                if ext in IGNORE_EXTENSIONS:
                    continue

                filepath = os.path.join(root, filename)
                results = scan_file(filepath)
                
                if results:
                    found_secrets = True
                    print(f"\n[!] POTENTIAL SECRET(S) IN: {filepath}")
                    for issue in results:
                        # Redact the matched secret in the output for safety
                        redacted_line = issue['content'].replace(issue['match'], "*****")
                        print(f"    Line {issue['line']}: {redacted_line}")

    print("-" * 60)
    if found_secrets:
        print("Scan complete. Potential secrets found. Please review and scrub before pushing.")
        sys.exit(1)
    else:
        print("Scan complete. No obvious secrets found.")
        sys.exit(0)

if __name__ == "__main__":
    main()
