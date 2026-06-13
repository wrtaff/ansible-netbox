#!/usr/bin/env python3
"""
================================================================================
Filename:       conftest.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3576

Purpose:
    Shared pytest fixtures for the pops-bot test suite. Provides env-var setup
    via monkeypatch (with get_settings cache cleared on setup and teardown), and
    factory fixtures for building mock Update and Context objects backed by
    unittest.mock so handler tests never require a live Telegram connection.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-bot
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/ -v

Revision History:
    1.0 - Initial test suite (B3). Trac #3576.
================================================================================
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure the pops-bot project root is importable regardless of invocation dir.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TEST_TOKEN = "test-token-abc123"
TEST_API_KEY = "test-api-key-xyz"
TEST_API_URL = "http://testserver"
TEST_ALLOWED_IDS = "1111,2222"


@pytest.fixture
def env_setup(monkeypatch):
    """Set required env vars and keep get_settings cache consistent.

    Sets TELEGRAM_BOT_TOKEN, POPS_API_KEY, TELEGRAM_ALLOWED_USER_IDS, and
    POPS_API_URL, then clears the lru_cache before the test runs and again on
    teardown so no state leaks between tests.
    """
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TEST_TOKEN)
    monkeypatch.setenv("POPS_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", TEST_ALLOWED_IDS)
    monkeypatch.setenv("POPS_API_URL", TEST_API_URL)

    from bot.config import get_settings
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


@pytest.fixture
def make_update():
    """Return a factory that builds a mock Telegram Update.

    The returned Update has:
      - effective_user.id  set to the supplied user_id
      - effective_message.text set to the supplied text
      - effective_message.reply_text as an AsyncMock (captures reply calls)
    """
    def _factory(user_id: int, text: str = ""):
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = user_id
        message = MagicMock()
        message.text = text
        message.reply_text = AsyncMock()
        update.effective_message = message
        return update

    return _factory


@pytest.fixture
def make_context():
    """Return a factory that builds a mock PTB Context.

    bot_data is exposed via context.application.bot_data (a plain dict).
    args is exposed via context.args (a list, used by some command handlers).
    """
    def _factory(bot_data: dict | None = None, args: list | None = None):
        context = MagicMock()
        context.application.bot_data = bot_data if bot_data is not None else {}
        context.args = args if args is not None else []
        return context

    return _factory
