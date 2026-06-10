#!/usr/bin/env python3
"""
================================================================================
Filename:       main.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    FastAPI application entry point for the Pops KMS REST API: the central
    programmatic interface to the Pops KMS for LAN/Tailscale clients (Home
    Assistant, Telegram bot per Trac #3576, ad-hoc curl). Mounts all routers
    registered in app.routers.ALL_ROUTERS under the /api prefix.

    Phase 1 endpoints (Trac #3577 blueprint):
        GET  /api/health   - liveness and pops-root status (no auth)
        POST /api/inbox    - timestamped capture to raw/journal/ + wiki/log.md
        GET  /api/search   - ripgrep over wiki/

Secrets:
    None - no credentials or secrets required (API key handling lives in
    app.auth / app.config)

Usage:
    Development (athena):
        cd ~/ansible-netbox/pops-api
        POPS_API_KEY=devkey python3 -m uvicorn app.main:app \
            --host 0.0.0.0 --port 8765

    Production: systemd unit pops-api.service (Phase 4, see ticket #3577).

Revision History:
    1.0 - Initial scaffold (Phase 1 subtask P1.1). Trac #3577.
================================================================================
"""

from fastapi import FastAPI

from app import API_VERSION
from app.routers import ALL_ROUTERS

app = FastAPI(
    title="Pops KMS API",
    description="Central REST API for the Pops Personal Knowledge Management System",
    version=API_VERSION,
)

for router in ALL_ROUTERS:
    app.include_router(router, prefix="/api")
