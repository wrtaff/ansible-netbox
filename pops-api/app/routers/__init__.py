#!/usr/bin/env python3
"""
================================================================================
Filename:       __init__.py (package: app.routers)
Version:        1.5
Author:         Claude Code
Last Modified:  2026-06-11
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
    1.5 - Register tickets router (P2.2). Trac #3585.
    1.4 - Register tasks router (P2.1). Trac #3585.
    1.3 - Register search router (P1.6). Trac #3577.
    1.2 - Register inbox router (P1.5). Trac #3577.
    1.1 - Register health router (P1.4). Trac #3577.
    1.0 - Initial scaffold with empty registry (Phase 1 subtask P1.1).
          Trac #3577.
================================================================================
"""

# Subtask owners: import your router module here and append to ALL_ROUTERS.
# Example:
#     from app.routers import health
#     ALL_ROUTERS = [health.router]

from app.routers import health
from app.routers import inbox
from app.routers import search
from app.routers import tasks
from app.routers import tickets

ALL_ROUTERS: list = [
    health.router,
    inbox.router,
    search.router,
    tasks.router,
    tickets.router,
]
