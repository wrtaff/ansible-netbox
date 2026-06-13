#!/usr/bin/env python3
"""
================================================================================
Filename:       handlers.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3576

Purpose:
    python-telegram-bot (v22, async) handlers for the Pops KMS Telegram bot.
    Each handler is a thin front end over the Pops REST API via bot.api_client:
    commands map to inbox/search/tasks/tickets/transcribe calls and reply with
    concise confirmations. Every handler is guarded by an authorization gate
    (allow-list of Telegram user IDs) and wraps its API calls so a backend or
    unexpected error becomes a user-facing reply rather than a raised exception
    into PTB.

Secrets:
    None directly - this module consumes configuration (including the API key)
    from bot.config via the shared PopsClient stored in application.bot_data.
    The secret values are documented and owned by bot.config; nothing here logs
    them.

Usage:
    Registered by bot.main. The shared PopsClient lives in
    application.bot_data["client"]; settings live in
    application.bot_data["settings"].

Revision History:
    1.0 - Initial implementation (B2). Trac #3576.
================================================================================
"""

import asyncio
import functools
import logging
import os
from typing import Awaitable, Callable, Optional

from telegram import Update
from telegram.ext import ContextTypes

from bot.api_client import PopsApiError, PopsClient
from bot.config import Settings, get_settings

logger = logging.getLogger("pops_bot.handlers")

# Telegram hard-caps messages at 4096 characters; chunk well under that.
_MAX_MESSAGE_CHARS = 4000
# Reject audio downloads larger than the API's upload ceiling (200 MiB).
_MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024

HandlerType = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


# ----- shared accessors ------------------------------------------------------


def _client(context: ContextTypes.DEFAULT_TYPE) -> PopsClient:
    return context.application.bot_data["client"]


def _settings(context: ContextTypes.DEFAULT_TYPE) -> Settings:
    return context.application.bot_data.get("settings") or get_settings()


# ----- authorization ---------------------------------------------------------


def restricted(handler: HandlerType) -> HandlerType:
    """Decorator: ignore updates from users not on the allow-list.

    Unauthorized updates are logged (user id only) and dropped silently - no
    reply is sent, so the bot reveals nothing to unknown users. An empty
    allow-list means nobody is authorized.
    """

    @functools.wraps(handler)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        user = update.effective_user
        allowed = _settings(context).allowed_user_ids
        if user is None or user.id not in allowed:
            logger.warning(
                "Ignoring update from unauthorized user id=%s",
                getattr(user, "id", "unknown"),
            )
            return
        await handler(update, context)

    return wrapper


# ----- error wrapping --------------------------------------------------------


async def _safe_reply(update: Update, text: str) -> None:
    message = update.effective_message
    if message is not None:
        await message.reply_text(text)


def guarded(handler: HandlerType) -> HandlerType:
    """Decorator: turn API/unexpected errors into user-facing replies.

    PopsApiError becomes "API error (<status>): <detail>"; any other exception
    becomes a generic failure message with the traceback logged. A handler
    never raises into PTB.
    """

    @functools.wraps(handler)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        try:
            await handler(update, context)
        except PopsApiError as exc:
            await _safe_reply(
                update, f"API error ({exc.status_code}): {exc.detail}"
            )
        except Exception:  # noqa: BLE001 - never let a handler raise into PTB
            logger.exception("Unexpected error in handler %s", handler.__name__)
            await _safe_reply(
                update, "Sorry, something went wrong handling that request."
            )

    return wrapper


# ----- helpers ---------------------------------------------------------------


def _command_args_text(update: Update) -> str:
    """Return everything after the command word, stripped."""
    text = (update.effective_message.text or "") if update.effective_message else ""
    parts = text.split(maxsplit=1)
    return parts[1].strip() if len(parts) > 1 else ""


def _chunk_text(text: str, size: int = _MAX_MESSAGE_CHARS) -> list[str]:
    if not text:
        return [""]
    return [text[i : i + size] for i in range(0, len(text), size)]


_HELP_TEXT = (
    "Pops KMS bot - capture and query the knowledge base.\n\n"
    "Plain text: captured to the inbox journal.\n"
    "/rfi <question> - capture a request for information.\n"
    "/todo <text> [*label ...] - create a task (words prefixed with * are labels).\n"
    "/trac <summary> | <description> - create a Trac ticket.\n"
    "/search <query> - search the wiki.\n"
    "/status - API health.\n"
    "/help - this message.\n\n"
    "Send a voice note, audio file, or video note to transcribe it."
)


# ----- command handlers ------------------------------------------------------


@restricted
@guarded
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _safe_reply(update, _HELP_TEXT)


@restricted
@guarded
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _safe_reply(update, _HELP_TEXT)


@restricted
@guarded
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    info = await _client(context).health()
    reply = (
        f"status: {info.get('status', '?')}\n"
        f"version: {info.get('version', '?')}\n"
        f"uptime: {info.get('uptime_seconds', '?')}s"
    )
    await _safe_reply(update, reply)


@restricted
@guarded
async def capture_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    text = (message.text or "").strip() if message else ""
    if not text:
        return
    result = await _client(context).inbox(text, source="telegram")
    journal_path = result.get("journal_path", "")
    await _safe_reply(update, f"Captured -> {os.path.basename(journal_path)}")


@restricted
@guarded
async def rfi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = _command_args_text(update)
    if not text:
        await _safe_reply(update, "Usage: /rfi <question>")
        return
    result = await _client(context).inbox(text, source="rfi")
    journal_path = result.get("journal_path", "")
    await _safe_reply(
        update, f"RFI captured -> {os.path.basename(journal_path)}"
    )


@restricted
@guarded
async def todo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = _command_args_text(update)
    if not raw:
        await _safe_reply(update, "Usage: /todo <text> [*label ...]")
        return
    labels: list[str] = []
    title_words: list[str] = []
    for token in raw.split():
        if token.startswith("*") and len(token) > 1:
            labels.append(token[1:])
        else:
            title_words.append(token)
    title = " ".join(title_words).strip()
    if not title:
        await _safe_reply(update, "Usage: /todo <text> [*label ...]")
        return
    result = await _client(context).create_task(title=title, labels=labels)
    await _safe_reply(update, f"Task created: {result.get('url', '(no url)')}")


@restricted
@guarded
async def trac(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = _command_args_text(update)
    if not raw:
        await _safe_reply(update, "Usage: /trac <summary> | <description>")
        return
    summary, sep, description = raw.partition("|")
    summary = summary.strip()
    description = description.strip() if sep else ""
    if not description:
        description = "Created via pops-bot (Telegram). Ref #3576."
    if not summary:
        await _safe_reply(update, "Usage: /trac <summary> | <description>")
        return
    result = await _client(context).create_ticket(
        summary=summary, description=description
    )
    await _safe_reply(update, f"Ticket created: {result.get('url', '(no url)')}")


@restricted
@guarded
async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = _command_args_text(update)
    if not query:
        await _safe_reply(update, "Usage: /search <query>")
        return
    result = await _client(context).search(query, max_results=5)
    matches = result.get("matches", [])
    if not matches:
        await _safe_reply(update, "No matches.")
        return
    lines = []
    for m in matches:
        line = f"{m.get('file', '?')}:{m.get('line', '?')} - {m.get('text', '')}"
        lines.append(line[:120])
    await _safe_reply(update, "\n".join(lines))


# ----- voice / audio transcription ------------------------------------------


def _pick_filename(update: Update) -> tuple[str, str]:
    """Return (file_id, filename) for a voice/audio/video_note message."""
    message = update.effective_message
    if message.voice is not None:
        return message.voice.file_id, "voice.ogg"
    if message.audio is not None:
        name = message.audio.file_name or "audio.mp3"
        return message.audio.file_id, name
    if message.video_note is not None:
        return message.video_note.file_id, "video_note.mp4"
    raise ValueError("message carries no voice, audio, or video note")


async def _poll_transcription(
    update: Update,
    client: PopsClient,
    job_id: str,
    poll_seconds: int,
    timeout: int,
) -> None:
    """Poll a transcription job until it finishes, then reply with the result.

    Run as a background task (asyncio.create_task) so it never blocks other
    updates regardless of the Application's concurrency setting.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    try:
        while True:
            await asyncio.sleep(poll_seconds)
            job = await client.transcribe_status(job_id)
            state = job.get("status")
            if state == "done":
                transcript = job.get("transcript_text") or "(empty transcript)"
                for chunk in _chunk_text(transcript):
                    await _safe_reply(update, chunk)
                return
            if state == "failed":
                err = job.get("error") or "unknown error"
                await _safe_reply(update, f"Transcription failed: {err}")
                return
            if asyncio.get_event_loop().time() > deadline:
                await _safe_reply(
                    update,
                    f"Transcription job {job_id} still running after "
                    f"{timeout}s; giving up polling.",
                )
                return
    except PopsApiError as exc:
        await _safe_reply(
            update, f"API error ({exc.status_code}): {exc.detail}"
        )
    except Exception:  # noqa: BLE001
        logger.exception("Error while polling transcription job %s", job_id)
        await _safe_reply(
            update, "Sorry, something went wrong polling the transcription."
        )


@restricted
@guarded
async def transcribe_media(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message = update.effective_message
    file_id, filename = _pick_filename(update)

    tg_file = await context.bot.get_file(file_id)
    file_size = getattr(tg_file, "file_size", None) or 0
    if file_size and file_size > _MAX_DOWNLOAD_BYTES:
        await _safe_reply(
            update,
            f"That file is too large ({file_size} bytes); max is "
            f"{_MAX_DOWNLOAD_BYTES} bytes.",
        )
        return

    data = bytes(await tg_file.download_as_bytearray())
    if len(data) > _MAX_DOWNLOAD_BYTES:
        await _safe_reply(
            update,
            f"That file is too large ({len(data)} bytes); max is "
            f"{_MAX_DOWNLOAD_BYTES} bytes.",
        )
        return

    caption: Optional[str] = message.caption.strip() if message.caption else None
    context_text = caption or None

    job = await _client(context).transcribe_upload(
        file_bytes=data, filename=filename, context=context_text
    )
    job_id = job.get("job_id", "")
    await _safe_reply(
        update, f"Transcription job {job_id} started; transcribing..."
    )

    settings = _settings(context)
    # Spawn polling as a background task so it does not block other updates.
    asyncio.create_task(
        _poll_transcription(
            update,
            _client(context),
            job_id,
            settings.transcribe_poll_seconds,
            settings.transcribe_timeout,
        )
    )
