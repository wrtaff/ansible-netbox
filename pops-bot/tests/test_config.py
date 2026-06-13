#!/usr/bin/env python3
"""
================================================================================
Filename:       test_config.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3576

Purpose:
    Tests for bot.config: verifies that get_settings() correctly reads and
    parses all supported environment variables, that _parse_user_ids handles
    malformed entries gracefully, and that safe defaults apply when env vars are
    absent.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-bot
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/test_config.py -v

Revision History:
    1.0 - Initial test suite (B3). Trac #3576.
================================================================================
"""

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_settings(monkeypatch, **env):
    """Clear the cache, set env vars from **env, return fresh settings."""
    from bot.config import get_settings
    get_settings.cache_clear()
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    settings = get_settings()
    get_settings.cache_clear()
    return settings


# ---------------------------------------------------------------------------
# allowed_user_ids parsing
# ---------------------------------------------------------------------------

def test_allowed_ids_parse_to_frozenset(monkeypatch):
    """Comma-separated IDs are parsed into a frozenset of ints."""
    s = _fresh_settings(monkeypatch, TELEGRAM_ALLOWED_USER_IDS="1111,2222")
    assert s.allowed_user_ids == frozenset({1111, 2222})


def test_allowed_ids_type_is_frozenset(monkeypatch):
    """allowed_user_ids is specifically a frozenset, not a set or list."""
    s = _fresh_settings(monkeypatch, TELEGRAM_ALLOWED_USER_IDS="42")
    assert isinstance(s.allowed_user_ids, frozenset)


def test_allowed_ids_single_entry(monkeypatch):
    """A single ID (no comma) parses correctly."""
    s = _fresh_settings(monkeypatch, TELEGRAM_ALLOWED_USER_IDS="9999")
    assert 9999 in s.allowed_user_ids
    assert len(s.allowed_user_ids) == 1


def test_allowed_ids_malformed_entries_tolerated(monkeypatch):
    """Non-integer entries are silently skipped; valid IDs still parse."""
    s = _fresh_settings(
        monkeypatch, TELEGRAM_ALLOWED_USER_IDS="1111,notanumber,2222,bad"
    )
    assert s.allowed_user_ids == frozenset({1111, 2222})


def test_allowed_ids_blank_entries_ignored(monkeypatch):
    """Extra commas (blank entries) are ignored without error."""
    s = _fresh_settings(monkeypatch, TELEGRAM_ALLOWED_USER_IDS=",1111,,2222,")
    assert s.allowed_user_ids == frozenset({1111, 2222})


def test_allowed_ids_empty_string_yields_empty_frozenset(monkeypatch):
    """An empty TELEGRAM_ALLOWED_USER_IDS means nobody is authorized."""
    s = _fresh_settings(monkeypatch, TELEGRAM_ALLOWED_USER_IDS="")
    assert s.allowed_user_ids == frozenset()


def test_allowed_ids_default_is_empty_frozenset(monkeypatch):
    """When the env var is absent entirely, the default is an empty frozenset."""
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    from bot.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    get_settings.cache_clear()
    assert s.allowed_user_ids == frozenset()


# ---------------------------------------------------------------------------
# URL and polling defaults
# ---------------------------------------------------------------------------

def test_api_url_default(monkeypatch):
    """Default POPS_API_URL is http://127.0.0.1:8765."""
    monkeypatch.delenv("POPS_API_URL", raising=False)
    from bot.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    get_settings.cache_clear()
    assert s.api_url == "http://127.0.0.1:8765"


def test_api_url_trailing_slash_stripped(monkeypatch):
    """Trailing slashes on POPS_API_URL are stripped."""
    s = _fresh_settings(monkeypatch, POPS_API_URL="http://myhost:9000/")
    assert s.api_url == "http://myhost:9000"


def test_transcribe_poll_seconds_default(monkeypatch):
    """Default transcribe poll interval is 5 seconds."""
    monkeypatch.delenv("POPS_BOT_TRANSCRIBE_POLL_SECONDS", raising=False)
    from bot.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    get_settings.cache_clear()
    assert s.transcribe_poll_seconds == 5


def test_transcribe_timeout_default(monkeypatch):
    """Default transcribe timeout is 1800 seconds."""
    monkeypatch.delenv("POPS_BOT_TRANSCRIBE_TIMEOUT", raising=False)
    from bot.config import get_settings
    get_settings.cache_clear()
    s = get_settings()
    get_settings.cache_clear()
    assert s.transcribe_timeout == 1800


def test_transcribe_poll_seconds_custom(monkeypatch):
    """Custom POPS_BOT_TRANSCRIBE_POLL_SECONDS is parsed as int."""
    s = _fresh_settings(monkeypatch, POPS_BOT_TRANSCRIBE_POLL_SECONDS="10")
    assert s.transcribe_poll_seconds == 10


def test_transcribe_timeout_custom(monkeypatch):
    """Custom POPS_BOT_TRANSCRIBE_TIMEOUT is parsed as int."""
    s = _fresh_settings(monkeypatch, POPS_BOT_TRANSCRIBE_TIMEOUT="3600")
    assert s.transcribe_timeout == 3600


# ---------------------------------------------------------------------------
# lru_cache isolation
# ---------------------------------------------------------------------------

def test_settings_are_cached(monkeypatch):
    """Two calls to get_settings() with the same env return the same object."""
    from bot.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("POPS_API_URL", "http://cached-test")
    s1 = get_settings()
    s2 = get_settings()
    get_settings.cache_clear()
    assert s1 is s2


def test_cache_clear_picks_up_new_env(monkeypatch):
    """After cache_clear(), a new env value is reflected in the next call."""
    from bot.config import get_settings
    monkeypatch.setenv("POPS_API_URL", "http://first")
    get_settings.cache_clear()
    s1 = get_settings()

    monkeypatch.setenv("POPS_API_URL", "http://second")
    get_settings.cache_clear()
    s2 = get_settings()
    get_settings.cache_clear()

    assert s1.api_url == "http://first"
    assert s2.api_url == "http://second"
