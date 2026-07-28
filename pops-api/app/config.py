#!/usr/bin/env python3
"""
================================================================================
Filename:       config.py
Version:        1.2
Author:         Claude Code
Last Modified:  2026-07-28
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
    POPS_UPLOAD_MAX_BYTES  Max accepted /api/transcribe upload size
                           (default: 209715200 = 200 MiB)
    POPS_TRANSCRIBE_SCRIPT Path to the transcription script
                           (default: /home/will/ansible-netbox/scripts/transcribe_audio.py)
    POPS_TRANSCRIBE_PYTHON Interpreter used to run the transcription script
                           (default: python3)
    POPS_TRANSCRIBE_TIMEOUT  Transcription subprocess timeout, seconds
                           (default: 3600)
    POPS_LOG_HOST          Short canonical host token used as the activity-log
                           path segment -- athena, ar0, ar1, titan2, ynh2
                           (default: this machine's hostname, normalized
                           through HOST_ALIASES)

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
    1.2 - Activity log is writer-partitioned: log_file resolves
          wiki/log/<host>/YYYY-MM.md per access; wiki/log.md is frozen and
          exposed read-only as legacy_log_file. Trac #4068/#4054.
    1.1 - Add transcription settings (P3.1). Trac #3596.
    1.0 - Initial scaffold (Phase 1 subtask P1.1). Trac #3577.
================================================================================
"""

import os
import socket
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

# Long inventory hostnames map to the short canonical token used as the log
# path segment. `agent-runner-pve6-01` and `ar0` are the same machine, and both
# spellings appear in the pre-migration log -- which is precisely why the
# segment must be normalized rather than taken from `hostname` verbatim, or one
# host ends up with two directories and the partition stops being one-per-host.
# See skills/core/pops.md § Concurrent Memory (Trac #4054).
HOST_ALIASES = {
    "agent-runner-pve6-01": "ar0",
    "agent-runner-pve5-01": "ar1",
}


def canonical_host(name: str) -> str:
    """Return the short canonical host token used as the log path segment."""
    short = name.split(".")[0].strip().lower()
    return HOST_ALIASES.get(short, short)


@dataclass(frozen=True)
class Settings:
    pops_root: Path
    api_key: str
    port: int
    inbox_max_bytes: int
    search_timeout: int
    upload_max_bytes: int
    transcribe_script: str
    transcribe_python: str
    transcribe_timeout: int
    log_host: str

    @property
    def journal_dir(self) -> Path:
        return self.pops_root / "raw" / "journal"

    @property
    def wiki_dir(self) -> Path:
        return self.pops_root / "wiki"

    @property
    def log_dir(self) -> Path:
        """This host's directory in the writer-partitioned activity log."""
        return self.pops_root / "wiki" / "log" / self.log_host

    @property
    def log_file(self) -> Path:
        """Today's month file for this host: wiki/log/<host>/YYYY-MM.md.

        Resolved on every access and deliberately never cached: the target
        changes at month rollover and this service is long-running, so a value
        captured at startup would keep writing into a stale month forever.

        Only this host writes this file, which is what makes concurrent appends
        across the fleet conflict-free by construction (Trac #4054).
        """
        return self.log_dir / f"{date.today():%Y-%m}.md"

    @property
    def legacy_log_file(self) -> Path:
        """The frozen pre-migration log. Read-only -- never opened for write."""
        return self.pops_root / "wiki" / "log.md"

    @property
    def uploads_dir(self) -> Path:
        return self.pops_root / "tmp" / "api-uploads"

    @property
    def jobs_dir(self) -> Path:
        return self.pops_root / "tmp" / "api-jobs"

    @property
    def transcripts_dir(self) -> Path:
        return self.pops_root / "raw" / "transcripts"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        pops_root=Path(os.environ.get("POPS_ROOT", "/home/will/pops")),
        api_key=os.environ.get("POPS_API_KEY", ""),
        port=int(os.environ.get("POPS_API_PORT", "8765")),
        inbox_max_bytes=int(os.environ.get("POPS_INBOX_MAX_BYTES", "65536")),
        search_timeout=int(os.environ.get("POPS_SEARCH_TIMEOUT", "10")),
        upload_max_bytes=int(os.environ.get("POPS_UPLOAD_MAX_BYTES", "209715200")),
        transcribe_script=os.environ.get(
            "POPS_TRANSCRIBE_SCRIPT",
            "/home/will/ansible-netbox/scripts/transcribe_audio.py",
        ),
        transcribe_python=os.environ.get("POPS_TRANSCRIBE_PYTHON", "python3"),
        transcribe_timeout=int(os.environ.get("POPS_TRANSCRIBE_TIMEOUT", "3600")),
        log_host=canonical_host(
            os.environ.get("POPS_LOG_HOST") or socket.gethostname()
        ),
    )
