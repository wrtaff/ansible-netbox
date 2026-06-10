#!/usr/bin/env python3
"""
================================================================================
Filename:       __init__.py (package: app)
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Package marker for the Pops KMS REST API application. Holds the single
    API_VERSION constant reported by /api/health and the FastAPI metadata.

Secrets:
    None - no credentials or secrets required

Usage:
    from app import API_VERSION

Revision History:
    1.0 - Initial scaffold (Phase 1 subtask P1.1). Trac #3577.
================================================================================
"""

API_VERSION = "0.1.0"
