#!/usr/bin/env python3
"""
================================================================================
Filename:       tasks.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-11
Context:        http://trac.home.arpa/ticket/3585

Purpose:
    POST /api/tasks endpoint for the Pops KMS REST API. Accepts a task title
    with optional description, project_id, labels, and due date; delegates to
    app.services.vikunja.create_vikunja_task; and returns the created task's
    ID, URL, and title on HTTP 201.

    Backend failures (VikunjaError or network exceptions surfaced by the
    service) are returned as HTTP 502. The raw Vikunja API token is never
    included in error detail strings.

Secrets:
    None - credentials are resolved inside app.services.vikunja, not here.

Usage:
    POST /api/tasks
    Headers: X-API-Key: <key>
    Body (JSON): {
        "title": "My task",            # required, non-blank
        "description": "",             # optional
        "project_id": null,            # optional int; null -> Inbox (project 1)
        "labels": [],                  # optional list of label name strings
        "due": null                    # optional ISO 8601 due-date string
    }
    Success: HTTP 201 {"task_id": 42, "url": "http://...", "title": "My task"}
    Errors:
        400  title is empty or whitespace-only
        401  X-API-Key header missing
        403  X-API-Key header value invalid
        422  missing required field (pydantic validation)
        502  Vikunja backend error or unreachable

Revision History:
    1.0 - Initial implementation (Phase 2 subtask P2.1). Trac #3585.
================================================================================
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import require_api_key
from app.services.vikunja import VikunjaError, create_vikunja_task

router = APIRouter(dependencies=[Depends(require_api_key)], tags=["actions"])


class TaskRequest(BaseModel):
    title: str
    description: str = ""
    project_id: int | None = None
    labels: list[str] = []
    due: str | None = None


class TaskResponse(BaseModel):
    task_id: int
    url: str
    title: str


@router.post("/tasks", status_code=201, response_model=TaskResponse)
def post_tasks(payload: TaskRequest) -> TaskResponse:
    """
    Create a Vikunja task from the supplied payload.

    Returns HTTP 201 with task_id, url, and title on success.
    Returns HTTP 400 if title is empty or whitespace-only.
    Returns HTTP 502 if the Vikunja backend is unreachable or returns an error.
    """
    if not payload.title.strip():
        raise HTTPException(
            status_code=400,
            detail="title must not be empty or whitespace-only",
        )

    try:
        result = create_vikunja_task(
            title=payload.title,
            description=payload.description,
            project_id=payload.project_id,
            labels=payload.labels,
            due=payload.due,
        )
    except VikunjaError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Vikunja backend error: {exc}",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Unexpected backend error: {exc}",
        ) from exc

    return TaskResponse(
        task_id=result["task_id"],
        url=result["url"],
        title=result["title"],
    )
