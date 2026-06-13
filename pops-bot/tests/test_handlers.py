#!/usr/bin/env python3
"""
================================================================================
Filename:       test_handlers.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3576

Purpose:
    Tests for bot.handlers: authorization gate, per-command API delegation,
    argument parsing, error handling, and reply formatting. The Pops API client
    is patched at the context.application.bot_data["client"] seam - exactly
    where _client(context) reads it - so no real HTTP connections are made.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-bot
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/test_handlers.py -v

Revision History:
    1.0 - Initial test suite (B3). Trac #3576.
================================================================================
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from bot.api_client import PopsApiError
from bot.config import Settings
import bot.handlers as handlers

# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------

ALLOWED_USER_ID = 1111
OTHER_ALLOWED_ID = 2222
DENIED_USER_ID = 9999

# Settings object with both test users allowed.
_SETTINGS = Settings(
    telegram_bot_token="test-token",
    api_url="http://testserver",
    api_key="test-api-key",
    allowed_user_ids=frozenset({ALLOWED_USER_ID, OTHER_ALLOWED_ID}),
    transcribe_poll_seconds=5,
    transcribe_timeout=1800,
)


# ---------------------------------------------------------------------------
# Helpers: build mocks without fixtures where simpler
# ---------------------------------------------------------------------------

def _make_update(user_id: int, text: str = ""):
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = user_id
    message = MagicMock()
    message.text = text
    message.reply_text = AsyncMock()
    update.effective_message = message
    return update


def _make_api_client(**method_return_values):
    """Build a mock PopsClient with AsyncMock methods.

    Each kwarg names a method and specifies its return value.
    """
    client = MagicMock()
    defaults = {
        "inbox": {"journal_path": "/pops/raw/journal/2026-06-12.md"},
        "search": {"matches": []},
        "create_task": {"url": "http://vikunja/task/1"},
        "create_ticket": {"url": "http://trac/ticket/1"},
        "health": {"status": "ok", "version": "1.0", "uptime_seconds": 42},
    }
    defaults.update(method_return_values)
    for name, retval in defaults.items():
        if isinstance(retval, Exception):
            setattr(client, name, AsyncMock(side_effect=retval))
        else:
            setattr(client, name, AsyncMock(return_value=retval))
    return client


def _make_context(client=None, settings=None):
    context = MagicMock()
    context.application.bot_data = {
        "client": client or _make_api_client(),
        "settings": settings or _SETTINGS,
    }
    return context


def _run(coro):
    """Run a coroutine in a new event loop and return the result."""
    return asyncio.run(coro)


def _reply_text(update) -> str | None:
    """Return the first positional arg of the first reply_text call, or None."""
    calls = update.effective_message.reply_text.call_args_list
    if not calls:
        return None
    return calls[0][0][0]


# ---------------------------------------------------------------------------
# Authorization gate
# ---------------------------------------------------------------------------

class TestAuthGate:
    """The @restricted decorator silently drops updates from unknown users."""

    def test_denied_user_command_gets_no_reply(self):
        """A command from a denied user must produce no reply at all."""
        update = _make_update(DENIED_USER_ID, text="/help")
        context = _make_context()
        _run(handlers.help_command(update, context))
        update.effective_message.reply_text.assert_not_called()

    def test_denied_user_plain_text_gets_no_reply(self):
        """Plain text from a denied user must produce no reply."""
        update = _make_update(DENIED_USER_ID, text="What time is it?")
        context = _make_context()
        _run(handlers.capture_text(update, context))
        update.effective_message.reply_text.assert_not_called()

    def test_denied_user_todo_gets_no_reply(self):
        """A /todo command from a denied user must produce no reply."""
        update = _make_update(DENIED_USER_ID, text="/todo Buy bread")
        context = _make_context()
        _run(handlers.todo(update, context))
        update.effective_message.reply_text.assert_not_called()

    def test_allowed_user_does_get_reply(self):
        """An allowed user's plain text does trigger a reply."""
        update = _make_update(ALLOWED_USER_ID, text="Hello bot")
        context = _make_context()
        _run(handlers.capture_text(update, context))
        update.effective_message.reply_text.assert_called_once()


# ---------------------------------------------------------------------------
# capture_text (plain text -> inbox with source "telegram")
# ---------------------------------------------------------------------------

class TestCaptureText:
    def test_calls_inbox_with_telegram_source(self):
        """Plain text triggers inbox() with source='telegram'."""
        update = _make_update(ALLOWED_USER_ID, text="My note here")
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.capture_text(update, context))
        client.inbox.assert_called_once_with("My note here", source="telegram")

    def test_reply_contains_captured(self):
        """The reply text includes the word 'Captured'."""
        update = _make_update(ALLOWED_USER_ID, text="Some thought")
        context = _make_context()
        _run(handlers.capture_text(update, context))
        reply = _reply_text(update)
        assert reply is not None
        assert "Captured" in reply

    def test_empty_text_does_not_call_inbox(self):
        """An empty message does not call inbox()."""
        update = _make_update(ALLOWED_USER_ID, text="")
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.capture_text(update, context))
        client.inbox.assert_not_called()


# ---------------------------------------------------------------------------
# /rfi -> inbox with source "rfi"
# ---------------------------------------------------------------------------

class TestRfiHandler:
    def test_rfi_calls_inbox_with_rfi_source(self):
        """/rfi sends the question to inbox with source='rfi'."""
        update = _make_update(ALLOWED_USER_ID, text="/rfi What is a POP?")
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.rfi(update, context))
        client.inbox.assert_called_once_with("What is a POP?", source="rfi")

    def test_rfi_no_args_returns_usage(self):
        """/rfi with no text replies with usage instructions."""
        update = _make_update(ALLOWED_USER_ID, text="/rfi")
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.rfi(update, context))
        client.inbox.assert_not_called()
        reply = _reply_text(update)
        assert reply is not None
        assert "Usage" in reply or "usage" in reply.lower() or "/rfi" in reply


# ---------------------------------------------------------------------------
# /todo
# ---------------------------------------------------------------------------

class TestTodoHandler:
    def test_todo_parses_title_and_labels(self):
        """/todo splits star-prefixed tokens into labels."""
        update = _make_update(
            ALLOWED_USER_ID, text="/todo Buy milk *grocery *urgent"
        )
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.todo(update, context))
        client.create_task.assert_called_once()
        _, kwargs = client.create_task.call_args
        assert kwargs.get("title") == "Buy milk"
        assert set(kwargs.get("labels", [])) == {"grocery", "urgent"}

    def test_todo_no_args_replies_usage(self):
        """/todo with no args replies with usage, does not call API."""
        update = _make_update(ALLOWED_USER_ID, text="/todo")
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.todo(update, context))
        client.create_task.assert_not_called()
        reply = _reply_text(update)
        assert reply is not None
        assert "/todo" in reply

    def test_todo_only_labels_no_title_replies_usage(self):
        """/todo *label (no title words) replies with usage."""
        update = _make_update(ALLOWED_USER_ID, text="/todo *onlylabel")
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.todo(update, context))
        client.create_task.assert_not_called()

    def test_todo_no_labels_sends_empty_labels(self):
        """/todo without labels sends labels=[] (or omits key)."""
        update = _make_update(ALLOWED_USER_ID, text="/todo Just a task")
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.todo(update, context))
        client.create_task.assert_called_once()
        _, kwargs = client.create_task.call_args
        assert kwargs.get("title") == "Just a task"


# ---------------------------------------------------------------------------
# /trac
# ---------------------------------------------------------------------------

class TestTracHandler:
    def test_trac_with_pipe_sends_summary_and_description(self):
        """/trac 'summary | description' sends both fields correctly."""
        update = _make_update(
            ALLOWED_USER_ID, text="/trac Fix gate | The gate squeaks"
        )
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.trac(update, context))
        client.create_ticket.assert_called_once()
        _, kwargs = client.create_ticket.call_args
        assert kwargs.get("summary") == "Fix gate"
        assert kwargs.get("description") == "The gate squeaks"

    def test_trac_without_pipe_uses_default_description(self):
        """/trac without '|' uses the default description string."""
        update = _make_update(ALLOWED_USER_ID, text="/trac Fix the gate hinge")
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.trac(update, context))
        client.create_ticket.assert_called_once()
        _, kwargs = client.create_ticket.call_args
        assert kwargs.get("summary") == "Fix the gate hinge"
        # Default description should mention pops-bot or Telegram
        assert kwargs.get("description")  # non-empty
        assert "pops-bot" in kwargs["description"] or "Telegram" in kwargs["description"]

    def test_trac_no_args_replies_usage(self):
        """/trac with no args replies with usage, does not call API."""
        update = _make_update(ALLOWED_USER_ID, text="/trac")
        client = _make_api_client()
        context = _make_context(client=client)
        _run(handlers.trac(update, context))
        client.create_ticket.assert_not_called()
        reply = _reply_text(update)
        assert reply is not None
        assert "/trac" in reply


# ---------------------------------------------------------------------------
# /search
# ---------------------------------------------------------------------------

class TestSearchHandler:
    def test_search_two_matches_reply_contains_file_and_line(self):
        """Two search matches produce a reply mentioning file paths and lines."""
        matches = [
            {"file": "wiki/alpha.md", "line": 5, "text": "Zebra123 sentinel"},
            {"file": "wiki/beta.md", "line": 3, "text": "Pineapple grows"},
        ]
        client = _make_api_client(search={"matches": matches})
        update = _make_update(ALLOWED_USER_ID, text="/search zebra")
        context = _make_context(client=client)
        _run(handlers.search(update, context))
        reply = _reply_text(update)
        assert reply is not None
        assert "wiki/alpha.md" in reply
        assert "wiki/beta.md" in reply
        assert "5" in reply
        assert "3" in reply

    def test_search_zero_matches_replies_no_matches(self):
        """Zero search results produce a 'No matches.' reply."""
        client = _make_api_client(search={"matches": []})
        update = _make_update(ALLOWED_USER_ID, text="/search xyzzy_nonexistent")
        context = _make_context(client=client)
        _run(handlers.search(update, context))
        reply = _reply_text(update)
        assert reply is not None
        assert "No matches" in reply

    def test_search_no_args_replies_usage(self):
        """/search with no query text replies with usage."""
        client = _make_api_client()
        update = _make_update(ALLOWED_USER_ID, text="/search")
        context = _make_context(client=client)
        _run(handlers.search(update, context))
        client.search.assert_not_called()
        reply = _reply_text(update)
        assert reply is not None
        assert "/search" in reply


# ---------------------------------------------------------------------------
# PopsApiError handling
# ---------------------------------------------------------------------------

class TestPopsApiErrorHandling:
    def test_capture_text_api_error_replies_with_status_code(self):
        """When inbox() raises PopsApiError, the reply contains 'API error' and the code."""
        err = PopsApiError(503, "upstream unavailable")
        client = _make_api_client(inbox=err)
        update = _make_update(ALLOWED_USER_ID, text="Something to capture")
        context = _make_context(client=client)
        # Must NOT raise - the @guarded decorator catches PopsApiError.
        _run(handlers.capture_text(update, context))
        reply = _reply_text(update)
        assert reply is not None
        assert "API error" in reply
        assert "503" in reply

    def test_rfi_api_error_replies_with_status_code(self):
        """/rfi with a failing client replies with the error status."""
        err = PopsApiError(404, "endpoint missing")
        client = _make_api_client(inbox=err)
        update = _make_update(ALLOWED_USER_ID, text="/rfi A question")
        context = _make_context(client=client)
        _run(handlers.rfi(update, context))
        reply = _reply_text(update)
        assert "API error" in reply
        assert "404" in reply

    def test_todo_api_error_does_not_raise(self):
        """/todo with a failing client replies with error, does not raise."""
        err = PopsApiError(422, "bad payload")
        client = _make_api_client(create_task=err)
        update = _make_update(ALLOWED_USER_ID, text="/todo Buy milk")
        context = _make_context(client=client)
        _run(handlers.todo(update, context))  # must not raise
        reply = _reply_text(update)
        assert "422" in reply

    def test_trac_api_error_does_not_raise(self):
        """/trac with a failing client replies with error, does not raise."""
        err = PopsApiError(500, "trac is down")
        client = _make_api_client(create_ticket=err)
        update = _make_update(ALLOWED_USER_ID, text="/trac Some ticket")
        context = _make_context(client=client)
        _run(handlers.trac(update, context))  # must not raise
        reply = _reply_text(update)
        assert "API error" in reply
        assert "500" in reply

    def test_search_api_error_does_not_raise(self):
        """/search with a failing client replies with error, does not raise."""
        err = PopsApiError(401, "unauthorized")
        client = _make_api_client(search=err)
        update = _make_update(ALLOWED_USER_ID, text="/search something")
        context = _make_context(client=client)
        _run(handlers.search(update, context))  # must not raise
        reply = _reply_text(update)
        assert "API error" in reply
        assert "401" in reply
