#!/usr/bin/env python3
"""
================================================================================
Filename:       tickets.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-11
Context:        http://trac.home.arpa/ticket/3585

Purpose:
    POST /api/tickets endpoint for the Pops KMS REST API. Accepts a JSON
    payload describing a Trac ticket, validates required fields, delegates
    creation to app.services.trac.create_trac_ticket, and returns the new
    ticket id and public URL on HTTP 201. TracError from the service layer is
    surfaced as HTTP 502 with a safe detail string.

Secrets:
    None - Trac credentials are managed entirely within app.services.trac;
           this router handles only request/response shaping.

Usage:
    POST /api/tickets
    Headers: X-API-Key: <key>
    Body (JSON): {
        "summary": "Fix the thing",
        "description": "**Details here.**",
        "component": "pops-kms",
        "priority": "minor",
        "keywords": "",
        "cc": "will",
        "type": "task",
        "markdown": true
    }
    Success:  HTTP 201 {"ticket_id": 1234, "url": "http://trac.gafla.us.com/ticket/1234"}
    Errors:
        400  summary or description is empty or whitespace-only
        401  X-API-Key header missing
        403  X-API-Key header value invalid
        422  missing required field (pydantic validation)
        502  Trac XML-RPC error (safe detail string, no credentials)

Revision History:
    1.0 - Initial implementation (Phase 2 subtask P2.2). Trac #3585.
================================================================================
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.auth import require_api_key
from app.services.trac import TracError, create_trac_ticket

router = APIRouter(dependencies=[Depends(require_api_key)], tags=["actions"])


class TicketRequest(BaseModel):
    # Allow both the alias ("type") and the field name ("ticket_type") so that
    # internal callers and tests can use either form.
    model_config = ConfigDict(populate_by_name=True)

    summary: str
    description: str
    component: str = "pops-kms"
    priority: str = "minor"
    keywords: str = ""
    cc: str = "will"
    # "type" is a Python builtin - use an alias so the field is safe to
    # reference in Python while the JSON key remains "type".
    ticket_type: str = Field(default="task", alias="type")
    markdown: bool = True


class TicketResponse(BaseModel):
    ticket_id: int
    url: str


@router.post("/tickets", status_code=201, response_model=TicketResponse)
def post_tickets(payload: TicketRequest) -> TicketResponse:
    """
    Create a new Trac ticket and return its id and public URL.

    Validates that summary and description are non-blank, then delegates to
    app.services.trac.create_trac_ticket. Returns HTTP 201 on success.

    Raises:
        HTTPException 400: summary or description is empty/whitespace-only.
        HTTPException 502: Trac XML-RPC or network error.
    """
    if not payload.summary.strip():
        raise HTTPException(
            status_code=400,
            detail="summary must not be empty or whitespace-only",
        )
    if not payload.description.strip():
        raise HTTPException(
            status_code=400,
            detail="description must not be empty or whitespace-only",
        )

    try:
        result = create_trac_ticket(
            summary=payload.summary,
            description=payload.description,
            component=payload.component,
            priority=payload.priority,
            keywords=payload.keywords,
            cc=payload.cc,
            ticket_type=payload.ticket_type,
            markdown=payload.markdown,
        )
    except TracError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return TicketResponse(ticket_id=result["ticket_id"], url=result["url"])
