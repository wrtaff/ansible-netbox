#!/usr/bin/env python3
"""
================================================================================
Filename:       __init__.py (package: app.routers)
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Router registry for the Pops KMS REST API. app.main iterates ALL_ROUTERS
    and mounts each under the /api prefix. Each endpoint subtask adds its
    module here: implement an APIRouter named `router` in a new module, then
    import it below and append it to ALL_ROUTERS. This keeps parallel subtask
    merges down to one import line and one list entry per endpoint.

Secrets:
    None - no credentials or secrets required

Usage:
    from app.routers import ALL_ROUTERS

Revision History:
    1.0 - Initial scaffold with empty registry (Phase 1 subtask P1.1).
          Trac #3577.
================================================================================
"""

# Subtask owners: import your router module here and append to ALL_ROUTERS.
# Example:
#     from app.routers import health
#     ALL_ROUTERS = [health.router]

ALL_ROUTERS: list = []
