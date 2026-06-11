#!/usr/bin/env python3
"""
================================================================================
Filename:       conftest.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Shared pytest fixtures for the Pops KMS REST API test suite. Builds an
    isolated, throwaway pops tree under pytest's tmp_path and points the app at
    it via the POPS_ROOT environment variable, so tests NEVER read or write the
    real /home/will/pops. Also configures a known API key and yields a
    fastapi TestClient with the settings cache primed and cleared.

Secrets:
    None - no credentials or secrets required (uses the throwaway test key
    "test-key-123", which grants nothing outside the temp fixture).

Usage:
    Fixtures are auto-discovered by pytest:
        def test_x(client, auth_headers): ...
        def test_y(temp_pops_root): ...

Revision History:
    1.0 - Initial test suite (Phase 1 subtask P1.7). Trac #3577.
================================================================================
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure the pops-api project root (parent of tests/) is importable so that
# `import app` works regardless of where pytest is invoked from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Known throwaway key used by the client fixture and auth tests.
TEST_API_KEY = "test-key-123"


@pytest.fixture
def temp_pops_root(tmp_path):
    """
    Build a minimal, isolated pops tree under tmp_path:

        <root>/raw/journal/                 (empty, writable journal dir)
        <root>/wiki/alpha.md                (searchable fixture content)
        <root>/wiki/beta.md                 (searchable fixture content)
        <root>/wiki/gamma.md                (searchable fixture content)
        <root>/wiki/log.md                  (empty)

    Returns the root Path. Nothing here touches the real /home/will/pops.
    """
    root = tmp_path / "pops"
    journal_dir = root / "raw" / "journal"
    wiki_dir = root / "wiki"
    journal_dir.mkdir(parents=True)
    wiki_dir.mkdir(parents=True)

    # alpha.md - holds the unique sentinel "Zebra123" at line 5 and the
    # shared token "Pineapple" at line 4.
    (wiki_dir / "alpha.md").write_text(
        "# Alpha\n"            # line 1
        "\n"                   # line 2
        "The quick brown fox jumps over.\n"  # line 3
        "Pineapple grows in alpha.\n"        # line 4
        "Zebra123 sentinel line.\n"          # line 5
        "Final alpha paragraph.\n",          # line 6
        encoding="utf-8",
    )

    # beta.md - second occurrence of the shared token "Pineapple".
    (wiki_dir / "beta.md").write_text(
        "# Beta\n"
        "\n"
        "Pineapple grows in beta too.\n"
        "Beta has foxes nearby.\n",
        encoding="utf-8",
    )

    # gamma.md - unrelated content; never matches the search tokens above.
    (wiki_dir / "gamma.md").write_text(
        "# Gamma\n"
        "\n"
        "Just gamma rays and nothing else.\n",
        encoding="utf-8",
    )

    # Empty running log; inbox captures append summary lines here.
    (wiki_dir / "log.md").write_text("", encoding="utf-8")

    return root


@pytest.fixture
def client(temp_pops_root, monkeypatch):
    """
    Yield a TestClient bound to the temp pops tree and the test API key.

    Sets POPS_ROOT and POPS_API_KEY via monkeypatch.setenv, clears the
    lru_cached settings so they are re-read, and clears the cache again on
    teardown so no state leaks between tests.
    """
    monkeypatch.setenv("POPS_ROOT", str(temp_pops_root))
    monkeypatch.setenv("POPS_API_KEY", TEST_API_KEY)

    from app.config import get_settings
    get_settings.cache_clear()

    from app.main import app
    with TestClient(app) as test_client:
        yield test_client

    get_settings.cache_clear()


@pytest.fixture
def auth_headers():
    """Valid X-API-Key header dict for protected endpoints."""
    return {"X-API-Key": TEST_API_KEY}
