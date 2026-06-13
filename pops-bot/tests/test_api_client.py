#!/usr/bin/env python3
"""
================================================================================
Filename:       test_api_client.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3576

Purpose:
    Tests for bot.api_client.PopsClient and PopsApiError. Uses httpx.MockTransport
    injected into the PopsClient's internal AsyncClient (_client attribute) to
    intercept HTTP calls without a live server. Verifies auth headers, JSON
    parsing, error handling, and per-endpoint request bodies.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-bot
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/test_api_client.py -v

Revision History:
    1.0 - Initial test suite (B3). Trac #3576.
================================================================================
"""

import asyncio
import json

import httpx
import pytest

from bot.api_client import PopsApiError, PopsClient

# ---------------------------------------------------------------------------
# Seam: inject MockTransport into PopsClient._client after construction.
# PopsClient creates httpx.AsyncClient in __init__ with no transport hook, so
# the cleanest approach is to replace _client post-construction with a new
# AsyncClient backed by httpx.MockTransport. This does not require any
# monkeypatching of the module - only the instance attribute is replaced.
# ---------------------------------------------------------------------------

TEST_API_KEY = "secret-key-1234"
BASE_URL = "http://testserver"


def _make_client(handler, api_key: str = TEST_API_KEY) -> PopsClient:
    """Build a PopsClient whose HTTP layer is backed by a mock handler.

    The handler receives an httpx.Request and must return an httpx.Response.
    """
    client = PopsClient(base_url=BASE_URL, api_key=api_key)
    transport = httpx.MockTransport(handler)
    # Replace the internal AsyncClient with one that uses the mock transport.
    # The base_url is kept consistent so relative paths resolve correctly.
    client._client = httpx.AsyncClient(
        base_url=BASE_URL,
        transport=transport,
        timeout=httpx.Timeout(5.0),
    )
    return client


def _json_response(status: int, body: dict) -> httpx.Response:
    content = json.dumps(body).encode()
    return httpx.Response(
        status,
        headers={"content-type": "application/json"},
        content=content,
    )


def _text_response(status: int, text: str) -> httpx.Response:
    return httpx.Response(status, text=text)


# ---------------------------------------------------------------------------
# PopsApiError
# ---------------------------------------------------------------------------

def test_pops_api_error_stores_status_and_detail():
    err = PopsApiError(404, "not found")
    assert err.status_code == 404
    assert err.detail == "not found"


def test_pops_api_error_message_format():
    err = PopsApiError(500, "server exploded")
    assert "500" in str(err)
    assert "server exploded" in str(err)


def test_pops_api_error_never_contains_api_key():
    """The API key must not appear in PopsApiError messages."""
    key = "supersecretkey"
    err = PopsApiError(403, "forbidden")
    assert key not in str(err)
    assert key not in err.detail


# ---------------------------------------------------------------------------
# Auth header
# ---------------------------------------------------------------------------

def test_authenticated_calls_send_api_key_header():
    """inbox() includes the X-API-Key header on its request."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return _json_response(200, {"journal_path": "/pops/raw/journal/test.md"})

    client = _make_client(handler, api_key=TEST_API_KEY)

    async def run():
        result = await client.inbox("hello", source="telegram")
        await client.aclose()
        return result

    asyncio.run(run())
    assert captured["headers"].get("x-api-key") == TEST_API_KEY


def test_health_does_not_send_api_key_header():
    """health() (unauthenticated) must NOT include an X-API-Key header."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        return _json_response(200, {"status": "ok"})

    client = _make_client(handler)

    async def run():
        result = await client.health()
        await client.aclose()
        return result

    asyncio.run(run())
    assert "x-api-key" not in captured["headers"]


# ---------------------------------------------------------------------------
# 2xx -> parsed JSON
# ---------------------------------------------------------------------------

def test_2xx_returns_parsed_json():
    """A 200 response body is returned as a dict."""
    body = {"journal_path": "/pops/raw/journal/2026-06-12.md", "id": 42}

    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(200, body)

    client = _make_client(handler)

    async def run():
        result = await client.inbox("test text")
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result == body


def test_2xx_empty_body_returns_none():
    """A 204 response (no body) returns None without raising."""
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(204)

    client = _make_client(handler)

    async def run():
        result = await client.health()
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result is None


# ---------------------------------------------------------------------------
# non-2xx -> PopsApiError
# ---------------------------------------------------------------------------

def test_non_2xx_raises_pops_api_error():
    """A 404 response raises PopsApiError."""
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(404, {"detail": "not found"})

    client = _make_client(handler)

    async def run():
        await client.health()
        await client.aclose()

    with pytest.raises(PopsApiError) as exc_info:
        asyncio.run(run())

    assert exc_info.value.status_code == 404


def test_non_2xx_detail_parsed_from_json_body():
    """PopsApiError.detail is extracted from the FastAPI {"detail": ...} body."""
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(422, {"detail": "validation failed"})

    client = _make_client(handler)

    async def run():
        await client.search("anything")
        await client.aclose()

    with pytest.raises(PopsApiError) as exc_info:
        asyncio.run(run())

    assert exc_info.value.detail == "validation failed"
    assert exc_info.value.status_code == 422


def test_non_2xx_plain_text_body_becomes_detail():
    """When the error body is plain text, it becomes the detail string."""
    def handler(request: httpx.Request) -> httpx.Response:
        return _text_response(503, "service unavailable")

    client = _make_client(handler)

    async def run():
        await client.health()
        await client.aclose()

    with pytest.raises(PopsApiError) as exc_info:
        asyncio.run(run())

    assert "service unavailable" in exc_info.value.detail


def test_pops_api_error_does_not_contain_api_key_on_error():
    """The API key must not appear in any PopsApiError raised from a response."""
    def handler(request: httpx.Request) -> httpx.Response:
        return _json_response(403, {"detail": "forbidden"})

    client = _make_client(handler, api_key=TEST_API_KEY)

    async def run():
        await client.inbox("x")
        await client.aclose()

    with pytest.raises(PopsApiError) as exc_info:
        asyncio.run(run())

    assert TEST_API_KEY not in str(exc_info.value)
    assert TEST_API_KEY not in exc_info.value.detail


# ---------------------------------------------------------------------------
# inbox endpoint
# ---------------------------------------------------------------------------

def test_inbox_sends_text_and_source():
    """inbox() posts {text, source} as JSON."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _json_response(200, {"journal_path": "/pops/raw/journal/x.md"})

    client = _make_client(handler)

    async def run():
        await client.inbox("My note", source="telegram")
        await client.aclose()

    asyncio.run(run())
    assert captured["body"]["text"] == "My note"
    assert captured["body"]["source"] == "telegram"


def test_inbox_rfi_source():
    """inbox() with source='rfi' sends source='rfi' in the body."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _json_response(200, {"journal_path": "/pops/raw/journal/x.md"})

    client = _make_client(handler)

    async def run():
        await client.inbox("What is X?", source="rfi")
        await client.aclose()

    asyncio.run(run())
    assert captured["body"]["source"] == "rfi"


# ---------------------------------------------------------------------------
# search endpoint
# ---------------------------------------------------------------------------

def test_search_sends_q_param():
    """search() passes the query as the 'q' URL parameter."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = dict(request.url.params)
        return _json_response(200, {"matches": []})

    client = _make_client(handler)

    async def run():
        await client.search("zebra", max_results=3)
        await client.aclose()

    asyncio.run(run())
    assert captured["params"]["q"] == "zebra"
    assert captured["params"]["max_results"] == "3"


# ---------------------------------------------------------------------------
# create_task endpoint
# ---------------------------------------------------------------------------

def test_create_task_sends_title_and_labels():
    """create_task() posts title and labels list in JSON body."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _json_response(201, {"url": "http://vikunja/task/1"})

    client = _make_client(handler)

    async def run():
        await client.create_task(title="Buy milk", labels=["grocery", "urgent"])
        await client.aclose()

    asyncio.run(run())
    assert captured["body"]["title"] == "Buy milk"
    assert captured["body"]["labels"] == ["grocery", "urgent"]


def test_create_task_omits_labels_when_empty():
    """create_task() does not send a 'labels' key when labels is empty."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _json_response(201, {"url": "http://vikunja/task/2"})

    client = _make_client(handler)

    async def run():
        await client.create_task(title="Simple task", labels=[])
        await client.aclose()

    asyncio.run(run())
    assert "labels" not in captured["body"]


# ---------------------------------------------------------------------------
# create_ticket endpoint
# ---------------------------------------------------------------------------

def test_create_ticket_sends_summary_and_description():
    """create_ticket() posts summary and description in JSON body."""
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return _json_response(201, {"url": "http://trac/ticket/42"})

    client = _make_client(handler)

    async def run():
        await client.create_ticket(summary="Fix gate", description="The gate squeaks")
        await client.aclose()

    asyncio.run(run())
    assert captured["body"]["summary"] == "Fix gate"
    assert captured["body"]["description"] == "The gate squeaks"
