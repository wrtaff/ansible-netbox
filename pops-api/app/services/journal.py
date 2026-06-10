#!/usr/bin/env python3
"""
================================================================================
Filename:       journal.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Journal and log-file append service for the Pops KMS REST API. Implements
    the timestamped-capture rule for network sources: resolves today's
    network-capture journal file, creates it with YAML frontmatter if absent,
    appends a timestamped entry, and dual-writes a summary line to wiki/log.md.
    All writes are append-only (open mode "a") for concurrency safety.

Secrets:
    None - no credentials or secrets required

Usage:
    from app.services.journal import append_capture
    result = append_capture(text="hello", source="curl")
    # result keys: journal_path, log_line, timestamp

Revision History:
    1.0 - Initial implementation (Phase 1 subtask P1.5). Trac #3577.
================================================================================
"""

from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings


def append_capture(text: str, source: str) -> dict:
    """
    Append a timestamped capture entry to today's network-capture journal file
    and add a summary line to wiki/log.md.

    Args:
        text:   Capture text body (must be non-empty; caller validates).
        source: Source label, e.g. "network", "curl", "telegram".

    Returns:
        dict with keys:
            journal_path  (str)  - absolute path to the journal file written
            log_line      (str)  - the line appended to wiki/log.md
            timestamp     (str)  - ISO 8601 UTC timestamp of the operation
    """
    settings = get_settings()
    now_local = datetime.now()
    now_utc = datetime.now(timezone.utc)

    date_str = now_local.strftime("%Y-%m-%d")
    time_str = now_local.strftime("%H:%M")
    iso_ts = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    # --- Resolve journal file path ---
    journal_dir: Path = settings.journal_dir
    journal_path: Path = journal_dir / f"{date_str}-network-capture.md"

    # --- Create journal file with frontmatter if it does not exist ---
    if not journal_path.exists():
        journal_dir.mkdir(parents=True, exist_ok=True)
        header = (
            "---\n"
            f"created: {date_str}\n"
            "source: pops-api\n"
            "---\n"
            "\n"
            f"# Network Capture {date_str}\n"
            "\n"
        )
        # Use "x" mode so a race-created file is not silently overwritten;
        # if another process wins the race the FileExistsError is swallowed and
        # we fall through to the append below.
        try:
            with open(journal_path, "x", encoding="utf-8") as fh:
                fh.write(header)
        except FileExistsError:
            pass

    # --- Append entry to journal file (append-only, concurrency-safe) ---
    entry = f"## {time_str} [{source}]\n\n{text}\n\n"
    with open(journal_path, "a", encoding="utf-8") as fh:
        fh.write(entry)

    # --- Build log line and append to wiki/log.md ---
    first_line = text.splitlines()[0] if text.splitlines() else text
    summary = first_line[:60]
    log_line = f"## [{date_str}] capture | {source} {summary}"

    log_file: Path = settings.log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as fh:
        fh.write(log_line + "\n")

    return {
        "journal_path": str(journal_path),
        "log_line": log_line,
        "timestamp": iso_ts,
    }
