#!/usr/bin/env python3
"""
================================================================================
Filename:       __init__.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3576

Purpose:
    Package marker for the pops-bot test suite. Makes tests/ a proper Python
    package so pytest discovers all test modules and intra-package imports work
    correctly.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-bot
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/ -v

Revision History:
    1.0 - Initial test suite (B3). Trac #3576.
================================================================================
"""
