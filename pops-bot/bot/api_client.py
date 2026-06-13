#!/usr/bin/env python3
"""
================================================================================
Filename:       api_client.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3576

Purpose:
    Async HTTP client wrapper around the Pops KMS REST API (Trac #3577) for the
    Telegram bot. PopsClient exposes one method per bot-facing endpoint
    (health, inbox, search, tasks, tickets, transcribe upload + status) over a
    shared httpx.AsyncClient with sane timeouts. Every authenticated call sends
    the X-API-Key header. Non-2xx responses are raised as PopsApiError carrying
    the HTTP status and the FastAPI {"detail": ...} string; the API key is never
    included in any error.

Secrets:
    POPS_API_KEY  (consumed from bot.config; never logged or placed in error
                  messages) - sent as the X-API-Key request header.

Usage:
    from bot.api_client import PopsClient, PopsApiError
    client = PopsClient(base_url="http://127.0.0.1:8765", api_key="...")
    info = await client.health()
    await client.aclose()

Revision History:
    1.0 - Initial implementation (B2). Trac #3576.
================================================================================
"""

from typing import Any, Optional

import httpx


class PopsApiError(Exception):
    """Raised when the Pops API returns a non-2xx response.

    Attributes:
        status_code: HTTP status code returned by the API (or 0 for transport
            errors where no response was received).
        detail: Human-readable detail, parsed from the FastAPI {"detail": ...}
            body when present. Never contains the API key.
    """

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"API error {status_code}: {detail}")


# Shared timeout profiles. Uploads may take longer to stream, so they get a
# more generous read timeout.
_DEFAULT_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=60.0, pool=5.0)
_UPLOAD_TIMEOUT = httpx.Timeout(connect=5.0, read=120.0, write=120.0, pool=5.0)


class PopsClient:
    """Thin async client for the Pops KMS REST API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=_DEFAULT_TIMEOUT,
        )

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    @property
    def _auth_headers(self) -> dict[str, str]:
        return {"X-API-Key": self._api_key}

    @staticmethod
    def _extract_detail(response: httpx.Response) -> str:
        """Pull a safe detail string out of a FastAPI error response."""
        try:
            body = response.json()
        except ValueError:
            text = response.text.strip()
            return text or response.reason_phrase or "unknown error"
        if isinstance(body, dict) and "detail" in body:
            detail = body["detail"]
            # FastAPI validation errors return a list of dicts; stringify them.
            return detail if isinstance(detail, str) else str(detail)
        return str(body)

    def _check(self, response: httpx.Response) -> Any:
        """Return parsed JSON for 2xx responses, else raise PopsApiError."""
        if response.is_success:
            if not response.content:
                return None
            try:
                return response.json()
            except ValueError:
                return None
        raise PopsApiError(response.status_code, self._extract_detail(response))

    # ----- endpoints ---------------------------------------------------------

    async def health(self) -> dict:
        """GET /api/health (no auth)."""
        response = await self._client.get("/api/health")
        return self._check(response)

    async def inbox(self, text: str, source: str = "telegram") -> dict:
        """POST /api/inbox - timestamped capture."""
        response = await self._client.post(
            "/api/inbox",
            json={"text": text, "source": source},
            headers=self._auth_headers,
        )
        return self._check(response)

    async def search(self, q: str, max_results: int = 5) -> dict:
        """GET /api/search - ripgrep over the wiki."""
        response = await self._client.get(
            "/api/search",
            params={"q": q, "max_results": max_results},
            headers=self._auth_headers,
        )
        return self._check(response)

    async def create_task(
        self,
        title: str,
        description: str = "",
        labels: Optional[list[str]] = None,
    ) -> dict:
        """POST /api/tasks - create a Vikunja task."""
        payload: dict[str, Any] = {"title": title, "description": description}
        if labels:
            payload["labels"] = labels
        response = await self._client.post(
            "/api/tasks",
            json=payload,
            headers=self._auth_headers,
        )
        return self._check(response)

    async def create_ticket(
        self,
        summary: str,
        description: str,
        **kw: Any,
    ) -> dict:
        """POST /api/tickets - create a Trac ticket."""
        payload: dict[str, Any] = {"summary": summary, "description": description}
        payload.update(kw)
        response = await self._client.post(
            "/api/tickets",
            json=payload,
            headers=self._auth_headers,
        )
        return self._check(response)

    async def transcribe_upload(
        self,
        file_bytes: bytes,
        filename: str,
        context: Optional[str] = None,
    ) -> dict:
        """POST /api/transcribe - multipart audio upload, returns a job."""
        files = {"file": (filename, file_bytes)}
        data = {"context": context} if context else None
        response = await self._client.post(
            "/api/transcribe",
            files=files,
            data=data,
            headers=self._auth_headers,
            timeout=_UPLOAD_TIMEOUT,
        )
        return self._check(response)

    async def transcribe_status(self, job_id: str) -> dict:
        """GET /api/transcribe/{job_id} - transcription job status."""
        response = await self._client.get(
            f"/api/transcribe/{job_id}",
            headers=self._auth_headers,
        )
        return self._check(response)
