#!/usr/bin/env python3
"""
================================================================================
Filename:       test_health.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Tests for GET /api/health: confirms the endpoint is reachable without
    authentication and reports status "ok", the API version string, the temp
    pops-root path, and readable/writable flags both true against the fixture
    tree.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-api
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/test_health.py -v

Revision History:
    1.0 - Initial test suite (Phase 1 subtask P1.7). Trac #3577.
================================================================================
"""

from app import API_VERSION


def test_health_no_auth_required(client):
    """Health check returns 200 with no X-API-Key header."""
    resp = client.get("/api/health")
    assert resp.status_code == 200


def test_health_status_ok(client):
    """Status is 'ok' when pops-root is readable."""
    body = client.get("/api/health").json()
    assert body["status"] == "ok"


def test_health_version_string(client):
    """Version matches the app's API_VERSION constant."""
    body = client.get("/api/health").json()
    assert body["version"] == API_VERSION
    assert isinstance(body["version"], str)


def test_health_pops_root_points_at_temp(client, temp_pops_root):
    """Reported pops_root is the temp fixture root, not the real /home/will/pops."""
    body = client.get("/api/health").json()
    assert body["pops_root"] == str(temp_pops_root)
    assert "/home/will/pops" != body["pops_root"]


def test_health_readable_and_writable(client):
    """Fixture tree is both readable and writable."""
    body = client.get("/api/health").json()
    assert body["pops_root_readable"] is True
    assert body["pops_root_writable"] is True


def test_health_uptime_is_int(client):
    """Uptime is reported as a non-negative integer."""
    body = client.get("/api/health").json()
    assert isinstance(body["uptime_seconds"], int)
    assert body["uptime_seconds"] >= 0
