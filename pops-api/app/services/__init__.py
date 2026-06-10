#!/usr/bin/env python3
"""
================================================================================
Filename:       __init__.py (package: app.services)
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Package marker for Pops KMS REST API service modules. Services hold the
    filesystem and subprocess logic (journal appends, ripgrep search, future
    transcription jobs) so routers stay thin request/response adapters.
    Phase 1 modules: journal.py (P1.5), ripgrep.py (P1.6).

Secrets:
    None - no credentials or secrets required

Revision History:
    1.0 - Initial scaffold (Phase 1 subtask P1.1). Trac #3577.
================================================================================
"""
