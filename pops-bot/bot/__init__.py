#!/usr/bin/env python3
"""
================================================================================
Filename:       __init__.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3576

Purpose:
    Package marker for the Pops KMS Telegram bot (pops-bot). The bot is a pure
    client of the Pops KMS REST API (Trac #3577); it owns no knowledge-base
    logic of its own. This module exposes the bot version string consumed by
    startup logging and the /status command.

Secrets:
    None - this module exposes only the version constant. The bot's secrets
    (TELEGRAM_BOT_TOKEN, POPS_API_KEY) are documented and owned by bot.config.

Usage:
    from bot import BOT_VERSION

Revision History:
    1.0 - Initial implementation (B2). Trac #3576.
================================================================================
"""

BOT_VERSION = "0.1.0"
