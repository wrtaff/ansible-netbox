#!/usr/bin/env python3
"""
================================================================================
Filename:       test_tasks.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-11
Context:        http://trac.home.arpa/ticket/3585

Purpose:
    Tests for POST /api/tasks: covers authentication (401/403), blank-title
    rejection (400), missing-field validation (422), the 201 happy path with
    full call-argument assertions (including all defaults), and the 502 error
    path when the Vikunja service raises VikunjaError. Every test monkeypatches
    app.routers.tasks.create_vikunja_task so the real Vikunja backend is never
    contacted.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-api
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/test_tasks.py -v

Revision History:
    1.0 - Initial test coverage (Phase 2 subtask P2.3). Trac #3585.
================================================================================
"""

import pytest

# Canned service response returned by the monkeypatched happy-path stub.
_CANNED_TASK = {
    "task_id": 42,
    "url": "http://todo.gafla.us.com/tasks/42",
    "title": "Buy milk",
}


def _no_real_backend(*args, **kwargs):
    """Defensive guard: raises immediately if the real service is ever called."""
    raise AssertionError("real Vikunja backend reached - test is missing a monkeypatch")


# ---------------------------------------------------------------------------
# Authentication / authorisation
# ---------------------------------------------------------------------------


def test_task_no_auth_header_401(client, monkeypatch):
    """Missing X-API-Key returns 401 before the service is invoked."""
    from app.routers import tasks as tasks_router

    monkeypatch.setattr(tasks_router, "create_vikunja_task", _no_real_backend)
    resp = client.post("/api/tasks", json={"title": "Something"})
    assert resp.status_code == 401


def test_task_wrong_key_403(client, monkeypatch):
    """An incorrect X-API-Key returns 403 before the service is invoked."""
    from app.routers import tasks as tasks_router

    monkeypatch.setattr(tasks_router, "create_vikunja_task", _no_real_backend)
    resp = client.post(
        "/api/tasks",
        json={"title": "Something"},
        headers={"X-API-Key": "not-the-right-key"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_task_blank_title_400(client, auth_headers, monkeypatch):
    """An empty string title is rejected with 400."""
    from app.routers import tasks as tasks_router

    monkeypatch.setattr(tasks_router, "create_vikunja_task", _no_real_backend)
    resp = client.post("/api/tasks", json={"title": ""}, headers=auth_headers)
    assert resp.status_code == 400


def test_task_whitespace_title_400(client, auth_headers, monkeypatch):
    """A whitespace-only title is rejected with 400."""
    from app.routers import tasks as tasks_router

    monkeypatch.setattr(tasks_router, "create_vikunja_task", _no_real_backend)
    resp = client.post("/api/tasks", json={"title": "   \t\n  "}, headers=auth_headers)
    assert resp.status_code == 400


def test_task_missing_title_field_422(client, auth_headers, monkeypatch):
    """Omitting the required 'title' field returns 422 (pydantic validation)."""
    from app.routers import tasks as tasks_router

    monkeypatch.setattr(tasks_router, "create_vikunja_task", _no_real_backend)
    resp = client.post(
        "/api/tasks",
        json={"description": "no title supplied"},
        headers=auth_headers,
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_task_happy_path_201_defaults(client, auth_headers, monkeypatch):
    """
    A minimal valid payload returns 201 with the canned response, and the
    service is called with the correct arguments including all defaults:
    description="", project_id=None, labels=[], due=None.
    """
    from app.routers import tasks as tasks_router

    captured_calls = []

    def fake_create_vikunja_task(**kwargs):
        captured_calls.append(kwargs)
        return _CANNED_TASK

    monkeypatch.setattr(tasks_router, "create_vikunja_task", fake_create_vikunja_task)

    resp = client.post(
        "/api/tasks",
        json={"title": "Buy milk"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    body = resp.json()
    assert body["task_id"] == 42
    assert body["url"] == _CANNED_TASK["url"]
    assert body["title"] == "Buy milk"

    # Exactly one call to the service.
    assert len(captured_calls) == 1
    call = captured_calls[0]

    # Required field passes through.
    assert call["title"] == "Buy milk"

    # Optional fields default correctly.
    assert call["description"] == ""
    assert call["project_id"] is None
    assert call["labels"] == []
    assert call["due"] is None


def test_task_happy_path_optional_fields_forwarded(client, auth_headers, monkeypatch):
    """
    Optional fields (description, project_id, labels, due) are forwarded to
    the service when supplied by the caller.
    """
    from app.routers import tasks as tasks_router

    captured_calls = []

    def fake_create_vikunja_task(**kwargs):
        captured_calls.append(kwargs)
        return {"task_id": 99, "url": "http://todo.gafla.us.com/tasks/99", "title": "Deploy API"}

    monkeypatch.setattr(tasks_router, "create_vikunja_task", fake_create_vikunja_task)

    resp = client.post(
        "/api/tasks",
        json={
            "title": "Deploy API",
            "description": "Run ansible playbook.",
            "project_id": 7,
            "labels": ["devops", "urgent"],
            "due": "2026-07-01T09:00:00",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201

    call = captured_calls[0]
    assert call["description"] == "Run ansible playbook."
    assert call["project_id"] == 7
    assert call["labels"] == ["devops", "urgent"]
    assert call["due"] == "2026-07-01T09:00:00"


# ---------------------------------------------------------------------------
# 502 error path
# ---------------------------------------------------------------------------


def test_task_502_on_vikunja_error(client, auth_headers, monkeypatch):
    """
    When the service raises VikunjaError the route returns 502, and the
    detail string does not contain the literal word 'token' (no credential
    leakage).
    """
    from app.routers import tasks as tasks_router
    from app.services.vikunja import VikunjaError

    def fail_vikunja(**kwargs):
        raise VikunjaError("connection refused to Vikunja backend")

    monkeypatch.setattr(tasks_router, "create_vikunja_task", fail_vikunja)

    resp = client.post("/api/tasks", json={"title": "Anything"}, headers=auth_headers)
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert "token" not in detail
