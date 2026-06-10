#!/usr/bin/env python3
"""
================================================================================
Filename:       search.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    GET /api/search endpoint for the Pops KMS REST API. Accepts a query string
    and optional tuning parameters, delegates to app.services.ripgrep for
    full-text search over the wiki directory, and returns structured JSON
    results.  Requires X-API-Key authentication on every request.

Secrets:
    None - no credentials or secrets required

Usage:
    GET /api/search?q=<query>[&max_results=20][&context=2]
    Header: X-API-Key: <key>

    Success (200):
        {
            "query":         "<original query string>",
            "total_matches": <int>,
            "truncated":     <bool>,
            "matches": [
                {
                    "file":           "<path relative to wiki_dir>",
                    "line":           <int>,
                    "text":           "<match line, rstripped>",
                    "context_before": ["<line>", ...],
                    "context_after":  ["<line>", ...]
                },
                ...
            ]
        }

    Error responses:
        400 - q is missing or blank
        401 - X-API-Key header absent
        403 - X-API-Key value invalid
        502 - ripgrep exited with an error (bad regex, I/O error, etc.)
        503 - API key not configured on server
        504 - ripgrep timed out

Revision History:
    1.0 - Initial implementation (Phase 1 subtask P1.6). Trac #3577.
================================================================================
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import require_api_key
from app.services.ripgrep import SearchError, SearchTimeout, search_wiki

router = APIRouter(
    dependencies=[Depends(require_api_key)],
    tags=["search"],
)


class MatchResult(BaseModel):
    file: str
    line: int
    text: str
    context_before: list[str]
    context_after: list[str]


class SearchResponse(BaseModel):
    query: str
    total_matches: int
    truncated: bool
    matches: list[MatchResult]


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., description="Search query (ripgrep regex)"),
    max_results: int = Query(
        default=20,
        ge=1,
        le=200,
        description="Maximum number of matches to return (1-200)",
    ),
    context: int = Query(
        default=2,
        ge=0,
        le=10,
        description="Lines of context before and after each match (0-10)",
    ),
) -> SearchResponse:
    """
    Full-text search over the Pops wiki using ripgrep.

    The query is passed directly to ripgrep as a regex with --smart-case, so
    lowercase queries are case-insensitive and any uppercase letter forces
    case-sensitive matching.  Invalid regex patterns result in a 502 error.
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query parameter 'q' must not be empty or whitespace")

    try:
        matches_raw, truncated = search_wiki(query=q, max_results=max_results, context=context)
    except SearchTimeout as exc:
        raise HTTPException(status_code=504, detail=f"Search timed out: {exc}") from exc
    except SearchError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Search backend error: {exc.stderr_snippet or str(exc)}",
        ) from exc

    matches = [MatchResult(**m) for m in matches_raw]

    return SearchResponse(
        query=q,
        total_matches=len(matches),
        truncated=truncated,
        matches=matches,
    )
