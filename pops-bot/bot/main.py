#!/usr/bin/env python3
"""
================================================================================
Filename:       main.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3576

Purpose:
    Entry point for the Pops KMS Telegram bot (pops-bot). Builds the
    python-telegram-bot Application, wires the shared PopsClient and settings
    into application.bot_data, registers all command and message handlers, and
    runs long-polling. build_application() constructs the app from explicit
    arguments so it is importable and testable without a Telegram token; only
    the __main__ path requires TELEGRAM_BOT_TOKEN and POPS_API_KEY (the process
    fails fast with a clear log and non-zero exit if either is unset).

Secrets:
    None directly - the token and API key are read from bot.config (env vars;
    systemd EnvironmentFile /etc/pops-bot/env in production). Neither value is
    ever logged; the startup line logs only the bot version and the API URL.

Usage:
    Development (athena, from the pops-bot directory):
        TELEGRAM_BOT_TOKEN=... POPS_API_KEY=... \
            /opt/venvs/gemini_projects/bin/python3 -m bot.main

    Production: systemd unit pops-bot.service, deployed by
    playbooks/deploy_pops_bot.yml.

Revision History:
    1.0 - Initial implementation (B2). Trac #3576.
================================================================================
"""

import logging
import sys

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot import BOT_VERSION
from bot import handlers
from bot.api_client import PopsClient
from bot.config import Settings, get_settings

logger = logging.getLogger("pops_bot.main")


async def _on_shutdown(application: Application) -> None:
    """Close the shared HTTP client cleanly on shutdown."""
    client = application.bot_data.get("client")
    if client is not None:
        await client.aclose()


def build_application(token: str, settings: Settings) -> Application:
    """Build and configure the PTB Application.

    Importable without a real token so the structure can be verified offline;
    the caller supplies the token and settings.
    """
    application = (
        ApplicationBuilder()
        .token(token)
        .post_shutdown(_on_shutdown)
        .build()
    )

    application.bot_data["settings"] = settings
    application.bot_data["client"] = PopsClient(
        base_url=settings.api_url, api_key=settings.api_key
    )

    application.add_handler(CommandHandler("start", handlers.start))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("status", handlers.status))
    application.add_handler(CommandHandler("todo", handlers.todo))
    application.add_handler(CommandHandler("trac", handlers.trac))
    application.add_handler(CommandHandler("search", handlers.search))
    application.add_handler(CommandHandler("rfi", handlers.rfi))

    # Voice notes, audio files, and video notes are transcribed.
    application.add_handler(
        MessageHandler(
            filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE,
            handlers.transcribe_media,
        )
    )

    # Any remaining plain text (non-command) is an inbox capture.
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND, handlers.capture_text
        )
    )

    return application


def main() -> int:
    """Run the bot. Returns a non-zero exit code on a fatal config error."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    settings = get_settings()

    if not settings.telegram_bot_token:
        logger.error(
            "TELEGRAM_BOT_TOKEN is not set; cannot start. "
            "Set it in /etc/pops-bot/env (production) or the environment."
        )
        return 1
    if not settings.api_key:
        logger.error(
            "POPS_API_KEY is not set; cannot start. "
            "Set it in /etc/pops-bot/env (production) or the environment."
        )
        return 1

    logger.info(
        "Starting pops-bot v%s; Pops API at %s",
        BOT_VERSION,
        settings.api_url,
    )

    application = build_application(settings.telegram_bot_token, settings)
    application.run_polling()
    return 0


if __name__ == "__main__":
    sys.exit(main())
