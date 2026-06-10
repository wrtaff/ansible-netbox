#!/usr/bin/env python3
"""
================================================================================
Filename:       inbox.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    POST /api/inbox capture endpoint for the Pops KMS REST API. Accepts a text
    payload with an optional source label, validates size and content, delegates
    to app.services.journal.append_capture, and returns the journal path, log
    line, and timestamp on success (HTTP 201).

Secrets:
    None - no credentials or secrets required

Usage:
    POST /api/inbox
    Headers: X-API-Key: <key>
    Body (JSON): {"text": "...", "source": "network"}
    Success: HTTP 201 {"journal_path": "...", "log_line": "...", "timestamp": "..."}
    Errors:
        400  text is empty or whitespace-only
        401  X-API-Key header missing
        403  X-API-Key header value invalid
        413  text exceeds inbox_max_bytes
        422  missing required field (pydantic validation)

Revision History:
    1.0 - Initial implementation (Phase 1 subtask P1.5). Trac #3577.
================================================================================
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_api_key
from app.config import get_settings
from app.services.journal import append_capture

router = APIRouter(dependencies=[Depends(require_api_key)], tags=["capture"])


class CaptureRequest(BaseModel):
    text: str
    source: str = "network"


class CaptureResponse(BaseModel):
    journal_path: str
    log_line: str
    timestamp: str


@router.post("/inbox", status_code=201, response_model=CaptureResponse)
def post_inbox(payload: CaptureRequest) -> CaptureResponse:
    """
    Capture a text payload into today's network-capture journal file and append
    a summary line to wiki/log.md.

    Returns HTTP 201 with journal_path, log_line, and ISO 8601 timestamp.
    """
    settings = get_settings()

    # 413 if payload exceeds configured byte limit
    if len(payload.text.encode("utf-8")) > settings.inbox_max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"text exceeds maximum size of {settings.inbox_max_bytes} bytes",
        )

    # 400 if text is empty or whitespace-only
    if not payload.text.strip():
        raise HTTPException(
            status_code=400,
            detail="text must not be empty or whitespace-only",
        )

    result = append_capture(text=payload.text, source=payload.source)

    return CaptureResponse(
        journal_path=result["journal_path"],
        log_line=result["log_line"],
        timestamp=result["timestamp"],
    )
