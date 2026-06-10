#!/usr/bin/env python3
"""
================================================================================
Filename:       config.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Central configuration for the Pops KMS REST API. All settings are read
    from environment variables with safe defaults for local development on
    athena. In production, values are injected by systemd via EnvironmentFile
    (/etc/pops-api/env, mode 0600).

Settings (environment variables):
    POPS_ROOT              Path to the pops KMS repo (default: /home/will/pops)
    POPS_API_KEY           Shared API key required by all endpoints except
                           /api/health (default: empty = all auth rejected)
    POPS_API_PORT          Listen port for uvicorn (default: 8765)
    POPS_INBOX_MAX_BYTES   Max accepted /api/inbox text size (default: 65536)
    POPS_SEARCH_TIMEOUT    ripgrep subprocess timeout, seconds (default: 10)

Secrets:
    POPS_API_KEY  (env var; systemd EnvironmentFile in production) - shared
                  client API key verified by app.auth. Never log its value.

Usage:
    from app.config import get_settings
    settings = get_settings()
    settings.pops_root  # pathlib.Path

    Tests may clear the cache after changing env vars:
    get_settings.cache_clear()

Revision History:
    1.0 - Initial scaffold (Phase 1 subtask P1.1). Trac #3577.
================================================================================
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    pops_root: Path
    api_key: str
    port: int
    inbox_max_bytes: int
    search_timeout: int

    @property
    def journal_dir(self) -> Path:
        return self.pops_root / "raw" / "journal"

    @property
    def wiki_dir(self) -> Path:
        return self.pops_root / "wiki"

    @property
    def log_file(self) -> Path:
        return self.pops_root / "wiki" / "log.md"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        pops_root=Path(os.environ.get("POPS_ROOT", "/home/will/pops")),
        api_key=os.environ.get("POPS_API_KEY", ""),
        port=int(os.environ.get("POPS_API_PORT", "8765")),
        inbox_max_bytes=int(os.environ.get("POPS_INBOX_MAX_BYTES", "65536")),
        search_timeout=int(os.environ.get("POPS_SEARCH_TIMEOUT", "10")),
    )
