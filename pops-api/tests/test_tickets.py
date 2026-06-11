#!/usr/bin/env python3
"""
================================================================================
Filename:       test_tickets.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-11
Context:        http://trac.home.arpa/ticket/3585

Purpose:
    Tests for POST /api/tickets: covers authentication (401/403), blank-summary
    and blank-description rejection (400), missing-field validation (422), the
    201 happy path with full call-argument assertions (including all defaults and
    the "type" JSON alias mapping to ticket_type), and the 502 error path when
    the Trac service raises TracError. Every test monkeypatches
    app.routers.tickets.create_trac_ticket so the real Trac backend is never
    contacted.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-api
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/test_tickets.py -v

Revision History:
    1.0 - Initial test coverage (Phase 2 subtask P2.3). Trac #3585.
================================================================================
"""

import pytest

# Canned service response returned by the monkeypatched happy-path stub.
_CANNED_TICKET = {
    "ticket_id": 9999,
    "url": "http://trac.gafla.us.com/ticket/9999",
}

# Minimal valid payload reused across multiple tests.
_VALID_PAYLOAD = {
    "summary": "Fix the widget",
    "description": "Widget is broken. Please fix.",
}


def _no_real_backend(*args, **kwargs):
    """Defensive guard: raises immediately if the real service is ever called."""
    raise AssertionError("real Trac backend reached - test is missing a monkeypatch")


# ---------------------------------------------------------------------------
# Authentication / authorisation
# ---------------------------------------------------------------------------


def test_ticket_no_auth_header_401(client, monkeypatch):
    """Missing X-API-Key returns 401 before the service is invoked."""
    from app.routers import tickets as tickets_router

    monkeypatch.setattr(tickets_router, "create_trac_ticket", _no_real_backend)
    resp = client.post("/api/tickets", json=_VALID_PAYLOAD)
    assert resp.status_code == 401


def test_ticket_wrong_key_403(client, monkeypatch):
    """An incorrect X-API-Key returns 403 before the service is invoked."""
    from app.routers import tickets as tickets_router

    monkeypatch.setattr(tickets_router, "create_trac_ticket", _no_real_backend)
    resp = client.post(
        "/api/tickets",
        json=_VALID_PAYLOAD,
        headers={"X-API-Key": "not-the-right-key"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_ticket_blank_summary_400(client, auth_headers, monkeypatch):
    """An empty string summary is rejected with 400."""
    from app.routers import tickets as tickets_router

    monkeypatch.setattr(tickets_router, "create_trac_ticket", _no_real_backend)
    resp = client.post(
        "/api/tickets",
        json={"summary": "", "description": "Some description."},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_ticket_whitespace_summary_400(client, auth_headers, monkeypatch):
    """A whitespace-only summary is rejected with 400."""
    from app.routers import tickets as tickets_router

    monkeypatch.setattr(tickets_router, "create_trac_ticket", _no_real_backend)
    resp = client.post(
        "/api/tickets",
        json={"summary": "   \t  ", "description": "Some description."},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_ticket_blank_description_400(client, auth_headers, monkeypatch):
    """An empty string description is rejected with 400."""
    from app.routers import tickets as tickets_router

    monkeypatch.setattr(tickets_router, "create_trac_ticket", _no_real_backend)
    resp = client.post(
        "/api/tickets",
        json={"summary": "Fix the widget", "description": ""},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_ticket_whitespace_description_400(client, auth_headers, monkeypatch):
    """A whitespace-only description is rejected with 400."""
    from app.routers import tickets as tickets_router

    monkeypatch.setattr(tickets_router, "create_trac_ticket", _no_real_backend)
    resp = client.post(
        "/api/tickets",
        json={"summary": "Fix the widget", "description": "\n\n  \t"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


def test_ticket_missing_summary_422(client, auth_headers, monkeypatch):
    """Omitting the required 'summary' field returns 422 (pydantic validation)."""
    from app.routers import tickets as tickets_router

    monkeypatch.setattr(tickets_router, "create_trac_ticket", _no_real_backend)
    resp = client.post(
        "/api/tickets",
        json={"description": "No summary supplied."},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_ticket_missing_description_422(client, auth_headers, monkeypatch):
    """Omitting the required 'description' field returns 422 (pydantic validation)."""
    from app.routers import tickets as tickets_router

    monkeypatch.setattr(tickets_router, "create_trac_ticket", _no_real_backend)
    resp = client.post(
        "/api/tickets",
        json={"summary": "No description supplied"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_ticket_happy_path_201_defaults(client, auth_headers, monkeypatch):
    """
    A minimal valid payload returns 201 with the canned response, and the
    service is called with correct defaults: component='pops-kms',
    priority='minor', keywords='', cc='will', ticket_type='task', markdown=True.
    """
    from app.routers import tickets as tickets_router

    captured_calls = []

    def fake_create_trac_ticket(**kwargs):
        captured_calls.append(kwargs)
        return _CANNED_TICKET

    monkeypatch.setattr(tickets_router, "create_trac_ticket", fake_create_trac_ticket)

    resp = client.post(
        "/api/tickets",
        json=_VALID_PAYLOAD,
        headers=auth_headers,
    )
    assert resp.status_code == 201

    body = resp.json()
    assert body["ticket_id"] == 9999
    assert body["url"] == _CANNED_TICKET["url"]

    # Exactly one call to the service.
    assert len(captured_calls) == 1
    call = captured_calls[0]

    # Required fields pass through.
    assert call["summary"] == "Fix the widget"
    assert call["description"] == "Widget is broken. Please fix."

    # Optional fields use their defaults.
    assert call["component"] == "pops-kms"
    assert call["priority"] == "minor"
    assert call["keywords"] == ""
    assert call["cc"] == "will"
    assert call["ticket_type"] == "task"
    assert call["markdown"] is True


def test_ticket_type_alias_maps_to_ticket_type(client, auth_headers, monkeypatch):
    """
    Sending 'type' in the JSON body (the Pydantic alias) correctly maps to
    ticket_type when forwarded to the service function.
    """
    from app.routers import tickets as tickets_router

    captured_calls = []

    def fake_create_trac_ticket(**kwargs):
        captured_calls.append(kwargs)
        return _CANNED_TICKET

    monkeypatch.setattr(tickets_router, "create_trac_ticket", fake_create_trac_ticket)

    resp = client.post(
        "/api/tickets",
        json={
            "summary": "Add a feature",
            "description": "We need this enhancement.",
            "type": "enhancement",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201

    call = captured_calls[0]
    # The "type" JSON alias must arrive at the service as ticket_type="enhancement".
    assert call["ticket_type"] == "enhancement"


def test_ticket_happy_path_optional_fields_forwarded(client, auth_headers, monkeypatch):
    """
    All optional fields are forwarded to the service when explicitly supplied.
    """
    from app.routers import tickets as tickets_router

    captured_calls = []

    def fake_create_trac_ticket(**kwargs):
        captured_calls.append(kwargs)
        return _CANNED_TICKET

    monkeypatch.setattr(tickets_router, "create_trac_ticket", fake_create_trac_ticket)

    resp = client.post(
        "/api/tickets",
        json={
            "summary": "Upgrade Postgres",
            "description": "We need Postgres 17.",
            "component": "infra",
            "priority": "major",
            "keywords": "postgres database",
            "cc": "will,ops",
            "type": "task",
            "markdown": False,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201

    call = captured_calls[0]
    assert call["component"] == "infra"
    assert call["priority"] == "major"
    assert call["keywords"] == "postgres database"
    assert call["cc"] == "will,ops"
    assert call["ticket_type"] == "task"
    assert call["markdown"] is False


# ---------------------------------------------------------------------------
# 502 error path
# ---------------------------------------------------------------------------


def test_ticket_502_on_trac_error(client, auth_headers, monkeypatch):
    """
    When the service raises TracError the route returns 502, and the detail
    string does not contain the literal word 'password' (no credential leakage).
    """
    from app.routers import tickets as tickets_router
    from app.services.trac import TracError

    def fail_trac(**kwargs):
        raise TracError("Trac XML-RPC fault 403: Forbidden")

    monkeypatch.setattr(tickets_router, "create_trac_ticket", fail_trac)

    resp = client.post("/api/tickets", json=_VALID_PAYLOAD, headers=auth_headers)
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert "password" not in detail
