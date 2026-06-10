#!/usr/bin/env python3
"""
================================================================================
Filename:       health.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Health-check endpoint for the Pops KMS REST API. Reports system status,
    version, uptime, and pops-root filesystem accessibility without requiring
    authentication.

Secrets:
    None - no credentials or secrets required

Usage:
    GET /api/health (no authentication required)
    Response: {
        "status": "ok" or "degraded",
        "version": "0.1.0",
        "uptime_seconds": 123,
        "pops_root": "/home/will/pops",
        "pops_root_readable": true,
        "pops_root_writable": true
    }

Revision History:
    1.0 - Initial implementation (Phase 1 subtask P1.4). Trac #3577.
================================================================================
"""

import os
import time

from fastapi import APIRouter
from pydantic import BaseModel

from app import API_VERSION
from app.config import get_settings

router = APIRouter(tags=["health"])

START_TIME = time.monotonic()


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: int
    pops_root: str
    pops_root_readable: bool
    pops_root_writable: bool


@router.get("/health")
def health_check() -> HealthResponse:
    """
    Health-check endpoint. Reports API status, version, uptime, and
    pops-root filesystem accessibility. No authentication required.
    """
    settings = get_settings()
    pops_root = settings.pops_root

    # Check readability: must be a directory and readable
    pops_root_readable = (
        pops_root.exists() and
        pops_root.is_dir() and
        os.access(pops_root, os.R_OK)
    )

    # Check writability: check journal_dir
    journal_dir = settings.journal_dir
    pops_root_writable = os.access(journal_dir, os.W_OK)

    # Status is "ok" if readable, otherwise "degraded"
    status = "ok" if pops_root_readable else "degraded"

    # Uptime in seconds
    uptime_seconds = int(time.monotonic() - START_TIME)

    return HealthResponse(
        status=status,
        version=API_VERSION,
        uptime_seconds=uptime_seconds,
        pops_root=str(pops_root),
        pops_root_readable=pops_root_readable,
        pops_root_writable=pops_root_writable,
    )
