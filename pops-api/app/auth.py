#!/usr/bin/env python3
"""
================================================================================
Filename:       auth.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    X-API-Key header authentication dependency for the Pops KMS REST API.
    Validates incoming requests against a shared server-side API key using
    constant-time comparison. Integrated into routers via
    dependencies=[Depends(require_api_key)].

Secrets:
    POPS_API_KEY  (env var via app.config; systemd EnvironmentFile in
                  production) - shared client API key compared in constant
                  time. Value is never logged.

Usage:
    from app.auth import require_api_key
    router = APIRouter(dependencies=[Depends(require_api_key)])

Revision History:
    1.0 - Initial implementation (Phase 1 subtask P1.3). Trac #3577.
================================================================================
"""

import hmac
from typing import Optional

from fastapi import Header, HTTPException

from app.config import get_settings


async def require_api_key(x_api_key: Optional[str] = Header(None)) -> None:
    """
    FastAPI dependency that validates the X-API-Key header.

    Raises:
        HTTPException 503: API key not configured on server.
        HTTPException 401: X-API-Key header is missing.
        HTTPException 403: X-API-Key header value is invalid.

    Returns:
        None on success.
    """
    settings = get_settings()

    # 503 if server-side key not configured
    if not settings.api_key:
        raise HTTPException(
            status_code=503,
            detail="API key not configured on server"
        )

    # 401 if header missing
    if x_api_key is None:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header"
        )

    # 403 if invalid (constant-time comparison)
    if not hmac.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )

    return None
