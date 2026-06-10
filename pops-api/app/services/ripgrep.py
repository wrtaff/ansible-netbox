#!/usr/bin/env python3
"""
================================================================================
Filename:       ripgrep.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-10
Context:        http://trac.home.arpa/ticket/3577

Purpose:
    Ripgrep-backed full-text search service for the Pops KMS REST API.
    Runs /usr/bin/rg as a subprocess over the wiki directory and parses its
    --json event stream into structured match dicts suitable for the
    GET /api/search response.

Secrets:
    None - no credentials or secrets required

Usage:
    from app.services.ripgrep import search_wiki, SearchTimeout, SearchError

    matches, truncated = search_wiki("Pops", max_results=20, context=2)
    # Each match: {"file": str, "line": int, "text": str,
    #              "context_before": list[str], "context_after": list[str]}

    # SearchTimeout raised when rg exceeds settings.search_timeout seconds.
    # SearchError raised when rg exits with code >= 2 (bad regex, I/O error).

Revision History:
    1.0 - Initial implementation (Phase 1 subtask P1.6). Trac #3577.
================================================================================
"""

import json
import subprocess
from pathlib import Path
from typing import Tuple

from app.config import get_settings


class SearchTimeout(Exception):
    """Raised when the ripgrep subprocess exceeds the configured timeout."""


class SearchError(Exception):
    """Raised when ripgrep exits with code 2+ (bad regex, I/O error, etc.)."""

    def __init__(self, message: str, stderr_snippet: str = "") -> None:
        super().__init__(message)
        self.stderr_snippet = stderr_snippet


def search_wiki(
    query: str,
    max_results: int = 20,
    context: int = 2,
) -> Tuple[list, bool]:
    """
    Search the wiki directory using ripgrep with JSON output.

    Runs: rg --json --smart-case -C <context> -- <query> <wiki_dir>

    Args:
        query:       Search string; ripgrep treats it as a regex.
        max_results: Maximum number of match dicts to return (hard cap).
        context:     Lines of context to include before and after each match.

    Returns:
        A tuple (matches, truncated).
          matches   - list of match dicts (see shape below).
          truncated - True when the result set was capped at max_results.

    Match dict shape::

        {
            "file":           str,        # path relative to wiki_dir
            "line":           int,        # 1-based line number of the match
            "text":           str,        # match line text, rstripped
            "context_before": list[str],  # lines before the match, rstripped
            "context_after":  list[str],  # lines after the match, rstripped
        }

    Raises:
        SearchTimeout: ripgrep did not complete within settings.search_timeout.
        SearchError:   ripgrep exited with code 2 or higher; carries a
                       stderr_snippet attribute (max 200 chars).
    """
    settings = get_settings()
    wiki_dir = settings.wiki_dir

    cmd = [
        "rg",
        "--json",
        "--smart-case",
        "-C", str(context),
        "--",
        query,
        str(wiki_dir),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            timeout=settings.search_timeout,
        )
    except subprocess.TimeoutExpired:
        raise SearchTimeout(
            f"ripgrep timed out after {settings.search_timeout}s"
        )

    # Exit code 1 = no matches (normal, not an error)
    if proc.returncode == 1:
        return [], False

    # Exit code 2+ = error (bad regex, unreadable path, etc.)
    if proc.returncode >= 2:
        stderr_raw = proc.stderr.decode("utf-8", errors="replace")
        snippet = stderr_raw[:200]
        raise SearchError(
            f"ripgrep error (exit {proc.returncode}): {snippet}",
            stderr_snippet=snippet,
        )

    # Parse the --json event stream (one JSON object per line).
    #
    # Event types emitted by rg:
    #   begin   - start of a file block
    #   context - a context line (before or after a match)
    #   match   - a matching line
    #   end     - end of a file block (with per-file stats)
    #   summary - final summary (we ignore it)
    #
    # Context lines between two matches are shared: they appear as
    # context_after for the preceding match AND context_before for the
    # following match.  The algorithm below implements that by keeping a
    # pending_before buffer that is populated from both pre-match context
    # events and from the context_after accumulation of the current match.

    matches: list = []
    truncated = False
    pending_before: list = []   # context lines accumulated before next match
    current_match: dict = {}    # match whose context_after is still open
    have_current = False        # sentinel (avoids None check on dict)

    for raw_line in proc.stdout.splitlines():
        if not raw_line:
            continue
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        etype = event.get("type")
        data = event.get("data", {})

        if etype == "begin":
            # New file block - discard any state left over from previous file.
            pending_before = []
            have_current = False
            current_match = {}

        elif etype == "context":
            text = data.get("lines", {}).get("text", "").rstrip()
            if not have_current:
                # Pre-match context - buffer it as before-context.
                pending_before.append(text)
            else:
                # Post-match context - add to current match's after-context
                # and also buffer it so it becomes before-context for the
                # next match (shared context window).
                current_match["context_after"].append(text)
                pending_before.append(text)

        elif etype == "match":
            # Finalize the previous open match before opening a new one.
            if have_current:
                matches.append(current_match)
                have_current = False
                if len(matches) >= max_results:
                    truncated = True
                    break

            file_text = data.get("path", {}).get("text", "")
            try:
                rel_path = str(Path(file_text).relative_to(wiki_dir))
            except ValueError:
                rel_path = file_text

            line_number = data.get("line_number", 0)
            text = data.get("lines", {}).get("text", "").rstrip()

            current_match = {
                "file": rel_path,
                "line": line_number,
                "text": text,
                "context_before": list(pending_before),
                "context_after": [],
            }
            pending_before = []
            have_current = True

        elif etype == "end":
            if have_current:
                matches.append(current_match)
                have_current = False
                if len(matches) >= max_results:
                    truncated = True
                    break
            pending_before = []
            current_match = {}

    return matches, truncated
