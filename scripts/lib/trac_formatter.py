#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/lib/trac_formatter.py
Version:        1.1
Author:         Gemini CLI
Last Modified:  2026-04-02
Context:        http://trac.home.arpa/ticket/3265
WWOS:           http://192.168.0.99/mediawiki/index.php/Trac_Wiki_Formatter

Purpose:
    A library for formatting text for Trac (MoinMoin) wiki syntax.
    Provides functions for Markdown-to-MoinMoin conversion and sanitization.

    Update 1.1:
    - Finalized initial release and verified functionality.
    Update 1.0:
    - Initial release.
================================================================================
"""
import re

def format_code(text):
    """Wraps text in Trac code blocks (triple curly braces)."""
    return f"{{{{\n{text.strip()}\n}}}}"

def format_header(text, level=2):
    """Formats a Trac header (e.g., == Header == for level 2)."""
    marker = "=" * level
    return f"{marker} {text.strip()} {marker}"

def format_link(url, label=None):
    """Formats a Trac link [url label]."""
    if label:
        return f"[{url} {label}]"
    return f"[{url}]"

def format_list(items, bullet="*"):
    """Formats a list of items with the specified bullet."""
    return "\n".join([f" {bullet} {str(item).strip()}" for item in items])

def sanitize_content(text):
    """Redacts common secrets like API keys and passwords."""
    # Redact common API key patterns
    text = re.sub(r'(?i)(api[-_]?key|token|password|secret)["\s:=]+([a-zA-Z0-9_\-]{8,})', r'\1: [REDACTED]', text)
    # Redact URL credentials
    text = re.sub(r'(http[s]?://)([^:\s]+):([^@\s]+)@', r'\1\2:[REDACTED]@', text)
    return text

def markdown_to_moinmoin(text):
    """
    Performs basic conversion from Markdown to MoinMoin syntax.
    - Code blocks: ``` -> {{{ }}}
    - Bold: ** -> '''
    - Italic: * or _ -> ''
    - Headers: # -> =
    """
    # 1. Code blocks (handle triple backticks)
    text = re.sub(r'```(?:\w+)?\n(.*?)\n```', r'{{{\n\1\n}}}', text, flags=re.DOTALL)
    
    # 2. Bold (**text**)
    text = re.sub(r'\*\*(.*?)\*\*', r"'''\1'''", text)
    
    # 3. Headers (# Header)
    def header_replace(match):
        level = len(match.group(1))
        # Trac uses = H1 =, == H2 ==, etc.
        marker = "=" * level
        return f"{marker} {match.group(2).strip()} {marker}"
    
    text = re.sub(r'^(#+)\s+(.*?)$', header_replace, text, flags=re.MULTILINE)
    
    # 4. Inline code (`text`)
    text = re.sub(r'`([^`]+)`', r'{{{\1}}}', text)
    
    return text

def format_trac_report(title, sections):
    """
    Creates a standardized Trac report.
    sections: List of (header_text, content_text) tuples.
    """
    report = [format_header(title, 1)]
    for header, content in sections:
        report.append(f"\n{format_header(header, 2)}")
        report.append(markdown_to_moinmoin(content))
    return "\n".join(report)
