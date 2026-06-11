#!/usr/bin/env python3
"""
================================================================================
Filename:       __init__.py (package: tests)
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Package marker for the Pops KMS REST API test suite. Presence of this file
    makes `tests` an importable package so pytest resolves shared fixtures from
    conftest.py and keeps the repo root (pops-api/) on sys.path for `import app`.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-api
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/ -v

Revision History:
    1.0 - Initial test suite (Phase 1 subtask P1.7). Trac #3577.
================================================================================
"""
