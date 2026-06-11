#!/usr/bin/env python3
"""
================================================================================
Filename:       test_inbox.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Tests for POST /api/inbox: a valid capture creates today's journal file
    with YAML frontmatter and a timestamped entry, appends exactly one summary
    line to wiki/log.md, and a second same-day capture appends without
    duplicating the frontmatter. Also covers the error paths: empty/whitespace
    text (400), oversize text (413), missing field (422), the default "network"
    source, and 60-char summary truncation.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-api
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/test_inbox.py -v

Revision History:
    1.0 - Initial test suite (Phase 1 subtask P1.7). Trac #3577.
================================================================================
"""

from pathlib import Path


def _journal_files(temp_pops_root):
    return sorted((temp_pops_root / "raw" / "journal").glob("*-network-capture.md"))


def test_valid_capture_creates_journal_and_log(client, temp_pops_root):
    """A valid capture returns 201, writes a journal file, and logs one line."""
    resp = client.post(
        "/api/inbox",
        json={"text": "Remember to water the plants", "source": "curl"},
        headers={"X-API-Key": "test-key-123"},
    )
    assert resp.status_code == 201
    body = resp.json()

    journal_path = Path(body["journal_path"])
    # The journal must live inside the temp tree, never the real pops root.
    assert str(temp_pops_root) in str(journal_path)
    assert journal_path.exists()

    journal_text = journal_path.read_text(encoding="utf-8")
    # YAML frontmatter present exactly once.
    assert journal_text.startswith("---\n")
    assert journal_text.count("source: pops-api") == 1
    assert journal_text.count("# Network Capture") == 1
    # Timestamped entry header "## HH:MM [source]".
    assert "[curl]" in journal_text
    import re
    assert re.search(r"^## \d{2}:\d{2} \[curl\]$", journal_text, re.MULTILINE)
    assert "Remember to water the plants" in journal_text

    # Exactly one summary line appended to wiki/log.md.
    log_text = (temp_pops_root / "wiki" / "log.md").read_text(encoding="utf-8")
    log_lines = [ln for ln in log_text.splitlines() if ln.strip()]
    assert len(log_lines) == 1
    assert log_lines[0] == body["log_line"]
    assert "capture | curl Remember to water the plants" in log_lines[0]


def test_second_capture_same_day_no_duplicate_frontmatter(client, temp_pops_root):
    """A second same-day capture appends without re-writing frontmatter."""
    headers = {"X-API-Key": "test-key-123"}
    client.post("/api/inbox", json={"text": "first entry", "source": "curl"}, headers=headers)
    client.post("/api/inbox", json={"text": "second entry", "source": "curl"}, headers=headers)

    files = _journal_files(temp_pops_root)
    assert len(files) == 1
    journal_text = files[0].read_text(encoding="utf-8")

    # Frontmatter / title written exactly once despite two captures.
    assert journal_text.count("source: pops-api") == 1
    assert journal_text.count("# Network Capture") == 1
    # Two timestamped entries.
    assert journal_text.count("[curl]") == 2
    assert "first entry" in journal_text
    assert "second entry" in journal_text

    # Two summary lines in the log.
    log_text = (temp_pops_root / "wiki" / "log.md").read_text(encoding="utf-8")
    log_lines = [ln for ln in log_text.splitlines() if ln.strip()]
    assert len(log_lines) == 2


def test_empty_text_400(client):
    """Empty text is rejected with 400."""
    resp = client.post("/api/inbox", json={"text": ""}, headers={"X-API-Key": "test-key-123"})
    assert resp.status_code == 400


def test_whitespace_text_400(client):
    """Whitespace-only text is rejected with 400."""
    resp = client.post("/api/inbox", json={"text": "   \n\t  "}, headers={"X-API-Key": "test-key-123"})
    assert resp.status_code == 400


def test_oversize_text_413(client, monkeypatch):
    """Text exceeding POPS_INBOX_MAX_BYTES is rejected with 413."""
    from app.config import get_settings

    monkeypatch.setenv("POPS_INBOX_MAX_BYTES", "10")
    get_settings.cache_clear()
    try:
        resp = client.post(
            "/api/inbox",
            json={"text": "this payload is definitely longer than ten bytes"},
            headers={"X-API-Key": "test-key-123"},
        )
        assert resp.status_code == 413
    finally:
        monkeypatch.delenv("POPS_INBOX_MAX_BYTES", raising=False)
        get_settings.cache_clear()


def test_missing_text_field_422(client):
    """Missing the required 'text' field is a pydantic validation error (422)."""
    resp = client.post("/api/inbox", json={"source": "curl"}, headers={"X-API-Key": "test-key-123"})
    assert resp.status_code == 422


def test_default_source_is_network(client, temp_pops_root):
    """Omitting source defaults to 'network'."""
    resp = client.post(
        "/api/inbox",
        json={"text": "no source supplied"},
        headers={"X-API-Key": "test-key-123"},
    )
    assert resp.status_code == 201
    assert "| network " in resp.json()["log_line"]

    journal_text = _journal_files(temp_pops_root)[0].read_text(encoding="utf-8")
    assert "[network]" in journal_text


def test_summary_truncated_to_60_chars(client):
    """Long first lines are truncated to 60 chars in the log summary."""
    long_text = "A" * 100
    resp = client.post(
        "/api/inbox",
        json={"text": long_text, "source": "curl"},
        headers={"X-API-Key": "test-key-123"},
    )
    assert resp.status_code == 201
    log_line = resp.json()["log_line"]
    # Summary portion is the trailing 60 'A's, not 61.
    assert log_line.endswith("A" * 60)
    assert "A" * 61 not in log_line
