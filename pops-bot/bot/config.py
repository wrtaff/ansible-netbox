#!/usr/bin/env python3
"""
================================================================================
Filename:       config.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3576

Purpose:
    Central configuration for the Pops KMS Telegram bot (pops-bot). All settings
    are read from environment variables with safe defaults for local use on
    athena. In production, values are injected by systemd via EnvironmentFile
    (/etc/pops-bot/env, mode 0640 root:will). Mirrors the pops-api config style:
    a frozen dataclass plus an lru_cache'd get_settings() accessor that tests can
    reset with get_settings.cache_clear().

Settings (environment variables):
    TELEGRAM_BOT_TOKEN              BotFather token for the Telegram bot. Required
                                   at runtime (default: empty = bot will not
                                   start; bot.main fails fast).
    POPS_API_URL                   Base URL of the Pops KMS REST API
                                   (default: http://127.0.0.1:8765)
    POPS_API_KEY                   Shared X-API-Key for the Pops API. Required
                                   (default: empty = bot.main fails fast).
    TELEGRAM_ALLOWED_USER_IDS      Comma-separated Telegram user IDs allowed to
                                   use the bot (default: empty = NOBODY allowed).
    POPS_BOT_TRANSCRIBE_POLL_SECONDS  Seconds between transcription status polls
                                   (default: 5).
    POPS_BOT_TRANSCRIBE_TIMEOUT    Max seconds to poll a transcription job before
                                   giving up (default: 1800).

Secrets:
    TELEGRAM_BOT_TOKEN  (env var; systemd EnvironmentFile /etc/pops-bot/env in
                        production) - BotFather token granting full control of
                        the Telegram bot. Never log its value.
    POPS_API_KEY        (env var; same EnvironmentFile) - shared client API key
                        sent as X-API-Key to the Pops API. Never log its value.

Usage:
    from bot.config import get_settings
    settings = get_settings()
    settings.api_url
    # Tests may reset the cache after changing env vars:
    get_settings.cache_clear()

Revision History:
    1.0 - Initial implementation (B2). Trac #3576.
================================================================================
"""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    api_url: str
    api_key: str
    allowed_user_ids: frozenset[int]
    transcribe_poll_seconds: int
    transcribe_timeout: int


def _parse_user_ids(raw: str) -> frozenset[int]:
    """Parse a comma-separated list of integer Telegram user IDs.

    Blank entries are ignored. Non-integer entries are skipped so a malformed
    value can never crash startup (an empty result means NOBODY is allowed,
    which is the safe default).
    """
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            ids.add(int(part))
        except ValueError:
            continue
    return frozenset(ids)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        telegram_bot_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
        api_url=os.environ.get("POPS_API_URL", "http://127.0.0.1:8765").rstrip("/"),
        api_key=os.environ.get("POPS_API_KEY", ""),
        allowed_user_ids=_parse_user_ids(
            os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
        ),
        transcribe_poll_seconds=int(
            os.environ.get("POPS_BOT_TRANSCRIBE_POLL_SECONDS", "5")
        ),
        transcribe_timeout=int(
            os.environ.get("POPS_BOT_TRANSCRIBE_TIMEOUT", "1800")
        ),
    )
