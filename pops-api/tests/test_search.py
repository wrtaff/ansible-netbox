#!/usr/bin/env python3
"""
================================================================================
Filename:       test_search.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Tests for GET /api/search (ripgrep-backed full-text search over wiki/):
    a known string returns its file/line plus context lists, a no-match query
    returns an empty result set, blank q is 400, a bad regex is 502, and
    max_results truncation works. Parameter validation (max_results, context)
    is checked at the route. The timeout path is covered two ways: a service
    unit test that forces subprocess.TimeoutExpired and asserts SearchTimeout,
    and a route test that monkeypatches search_wiki to raise SearchTimeout and
    asserts 504.

    Requires the `rg` binary (installed at /usr/bin/rg).

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-api
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/test_search.py -v

Revision History:
    1.0 - Initial test suite (Phase 1 subtask P1.7). Trac #3577.
================================================================================
"""

import subprocess

import pytest


def test_known_string_returns_file_line_and_context(client, auth_headers):
    """A unique token returns its file, line number, and context lists."""
    resp = client.get("/api/search", params={"q": "Zebra123"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()

    assert body["query"] == "Zebra123"
    assert body["total_matches"] == 1
    assert body["truncated"] is False

    match = body["matches"][0]
    assert match["file"] == "alpha.md"
    assert match["line"] == 5
    assert "Zebra123" in match["text"]
    # Context lists are present and carry the surrounding fixture lines.
    assert isinstance(match["context_before"], list)
    assert isinstance(match["context_after"], list)
    assert "Pineapple grows in alpha." in match["context_before"]
    assert "Final alpha paragraph." in match["context_after"]


def test_no_match_returns_empty_result(client, auth_headers):
    """A query with no matches returns a well-formed empty result."""
    resp = client.get("/api/search", params={"q": "Zucchini999"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_matches"] == 0
    assert body["matches"] == []
    assert body["truncated"] is False


def test_empty_query_400(client, auth_headers):
    """A blank q value is rejected with 400."""
    resp = client.get("/api/search", params={"q": ""}, headers=auth_headers)
    assert resp.status_code == 400


def test_bad_regex_502(client, auth_headers):
    """An invalid regex makes ripgrep error out, surfaced as 502."""
    resp = client.get("/api/search", params={"q": "foo(bar"}, headers=auth_headers)
    assert resp.status_code == 502


def test_max_results_truncation(client, auth_headers):
    """A token in two files with max_results=1 returns one match, truncated."""
    resp = client.get(
        "/api/search",
        params={"q": "Pineapple", "max_results": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_matches"] == 1
    assert body["truncated"] is True


def test_max_results_zero_422(client, auth_headers):
    """max_results below the allowed minimum (ge=1) is a validation error."""
    resp = client.get(
        "/api/search",
        params={"q": "Pineapple", "max_results": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_context_out_of_range_422(client, auth_headers):
    """context above the allowed maximum (le=10) is a validation error."""
    resp = client.get(
        "/api/search",
        params={"q": "Pineapple", "context": 99},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_search_requires_auth(client):
    """Search is a protected endpoint; missing key returns 401."""
    resp = client.get("/api/search", params={"q": "Pineapple"})
    assert resp.status_code == 401


def test_service_timeout_raises_searchtimeout(temp_pops_root, monkeypatch):
    """Service-level: subprocess.TimeoutExpired is mapped to SearchTimeout."""
    monkeypatch.setenv("POPS_ROOT", str(temp_pops_root))

    from app.config import get_settings
    from app.services import ripgrep

    get_settings.cache_clear()

    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["rg"], timeout=10)

    monkeypatch.setattr(ripgrep.subprocess, "run", fake_run)
    try:
        with pytest.raises(ripgrep.SearchTimeout):
            ripgrep.search_wiki("anything")
    finally:
        get_settings.cache_clear()


def test_route_timeout_returns_504(client, auth_headers, monkeypatch):
    """Route-level: a SearchTimeout from the service surfaces as 504."""
    from app.routers import search as search_router
    from app.services.ripgrep import SearchTimeout

    def fake_search(*args, **kwargs):
        raise SearchTimeout("ripgrep timed out after 10s")

    monkeypatch.setattr(search_router, "search_wiki", fake_search)
    resp = client.get("/api/search", params={"q": "Pineapple"}, headers=auth_headers)
    assert resp.status_code == 504
