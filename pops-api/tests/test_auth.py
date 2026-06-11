#!/usr/bin/env python3
"""
================================================================================
Filename:       test_auth.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Tests for the X-API-Key authentication dependency (app.auth.require_api_key)
    exercised through a protected endpoint (POST /api/inbox): missing header ->
    401, wrong key -> 403, valid key -> success, and server-side key unset ->
    503.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-api
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/test_auth.py -v

Revision History:
    1.0 - Initial test suite (Phase 1 subtask P1.7). Trac #3577.
================================================================================
"""

from tests.conftest import TEST_API_KEY


def test_missing_api_key_401(client):
    """No X-API-Key header on a protected endpoint returns 401."""
    resp = client.post("/api/inbox", json={"text": "hello"})
    assert resp.status_code == 401


def test_wrong_api_key_403(client):
    """A non-matching X-API-Key value returns 403."""
    resp = client.post(
        "/api/inbox",
        json={"text": "hello"},
        headers={"X-API-Key": "definitely-not-the-key"},
    )
    assert resp.status_code == 403


def test_valid_api_key_passes(client, auth_headers):
    """The correct key passes auth and the capture succeeds (201)."""
    resp = client.post(
        "/api/inbox",
        json={"text": "authorized capture"},
        headers=auth_headers,
    )
    assert resp.status_code == 201


def test_server_key_unset_503(client, auth_headers, monkeypatch):
    """When the server key is unset, auth short-circuits with 503."""
    from app.config import get_settings

    monkeypatch.setenv("POPS_API_KEY", "")
    get_settings.cache_clear()
    try:
        resp = client.post(
            "/api/inbox",
            json={"text": "hello"},
            headers=auth_headers,
        )
        assert resp.status_code == 503
    finally:
        # Restore the configured key for any later cache reads in teardown.
        monkeypatch.setenv("POPS_API_KEY", TEST_API_KEY)
        get_settings.cache_clear()
