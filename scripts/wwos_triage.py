#!/usr/bin/env python3
"""
================================================================================
Filename:       wwos_triage.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-07-12
Context:        http://trac.gafla.us.com/ticket/3839
WWOS:           N/A (meta-tooling, not KMS content)

Purpose:
    Monthly local, LLM-agnostic triage of pops/wiki/ for notes that have gone
    stale (no git activity in STALE_DAYS) and may be ready to graduate from
    Pops (active working surface) to WWOS (institutional memory). Never
    writes to WWOS. Only proposes candidates by posting a comment to the
    tracking Trac ticket (#3839) for human review/approval.

    Summary line per candidate: frontmatter `description:` if present,
    else first H1 heading, else the filename.

Usage:
    python3 wwos_triage.py [--wiki-dir PATH] [--stale-days N] [--dry-run]
================================================================================
"""
import argparse
import os
import re
import subprocess
import sys
import time

DEFAULT_WIKI_DIR = "/home/will/pops/wiki"
DEFAULT_STALE_DAYS = 90
TRAC_TICKET_ID = 3839
TRAC_TICKET_URL = f"http://trac.gafla.us.com/ticket/{TRAC_TICKET_ID}"
EMAIL_TO = "wrtaff@gmail.com"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
UPDATE_SCRIPT = os.path.join(SCRIPT_DIR, "update_trac_ticket.py")
GWS_MANAGER = os.path.join(SCRIPT_DIR, "google_workspace_manager.py")

# Meta/infrastructure files and directories that are not candidate "notes"
EXCLUDE_NAMES = {"index.md", "log.md", "kms-layout.md", "rfi-log.md"}
EXCLUDE_DIR_PREFIXES = ("context/", "assets/")


def git_last_commit_epoch(repo_dir, relpath):
    """Return the epoch seconds of the last commit touching relpath, or None if untracked."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%ct", "--", relpath],
            cwd=repo_dir, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return int(out) if out else None
    except (subprocess.CalledProcessError, ValueError):
        return None


def extract_summary(filepath):
    """Frontmatter description: -> first H1 heading -> filename."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        return os.path.basename(filepath)

    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if fm_match:
        desc_match = re.search(r"^description:\s*(.+)$", fm_match.group(1), re.MULTILINE)
        if desc_match:
            return desc_match.group(1).strip().strip('"').strip("'")
        body = text[fm_match.end():]
    else:
        body = text

    heading_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    if heading_match:
        return heading_match.group(1).strip()

    return os.path.basename(filepath)


def find_candidates(wiki_dir, stale_days):
    # wiki/ is its own git repository (athena:/home/will/git/pops-kms.git),
    # separate from the pops repo -- git history must be resolved against it.
    repo_dir = wiki_dir.rstrip("/")
    cutoff = time.time() - (stale_days * 86400)
    candidates = []

    for root, _dirs, files in os.walk(wiki_dir):
        for fname in files:
            if not fname.endswith(".md") or fname in EXCLUDE_NAMES:
                continue
            fullpath = os.path.join(root, fname)
            wiki_relpath = os.path.relpath(fullpath, wiki_dir)
            if wiki_relpath.startswith(EXCLUDE_DIR_PREFIXES):
                continue

            last_commit = git_last_commit_epoch(repo_dir, wiki_relpath)
            if last_commit is None or last_commit > cutoff:
                continue

            age_days = int((time.time() - last_commit) / 86400)
            summary = extract_summary(fullpath)
            candidates.append((wiki_relpath, age_days, summary))

    candidates.sort(key=lambda c: -c[1])
    return candidates


def build_comment(candidates, stale_days):
    lines = [
        f"== Pops -> WWOS triage: {len(candidates)} candidate(s) (no git activity in {stale_days}+ days) ==",
        "",
        "Proposed for review -- not auto-published to WWOS:",
        "",
    ]
    for relpath, age_days, summary in candidates:
        lines.append(f" * '''{relpath}''' ({age_days}d stale) -- {summary}")
    return "\n".join(lines)


def notify_via_email(subject, body):
    """Best-effort email notification so a run is never silent. Never blocks the main flow."""
    try:
        result = subprocess.run(
            [sys.executable, GWS_MANAGER, "gmail-send", EMAIL_TO, subject, body],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(f"Email notification failed: {result.stderr}", file=sys.stderr)
        else:
            print("Notification emailed.")
    except Exception as e:
        print(f"Email notification failed: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Monthly Pops-to-WWOS triage.")
    parser.add_argument("--wiki-dir", default=DEFAULT_WIKI_DIR)
    parser.add_argument("--stale-days", type=int, default=DEFAULT_STALE_DAYS)
    parser.add_argument("--dry-run", action="store_true", help="Print the comment instead of posting to Trac / emailing.")
    args = parser.parse_args()

    candidates = find_candidates(args.wiki_dir, args.stale_days)

    if not candidates:
        msg = f"wwos_triage ran on {time.strftime('%Y-%m-%d')} -- no candidates found (nothing posted, no changes made)."
        print(msg)
        if not args.dry_run:
            notify_via_email("Pops -> WWOS triage: no candidates this run", msg)
        return

    comment = build_comment(candidates, args.stale_days)

    if args.dry_run:
        print(comment)
        return

    comment_file = "/tmp/wwos_triage_comment.txt"
    with open(comment_file, "w", encoding="utf-8") as f:
        f.write(comment)

    result = subprocess.run(
        [sys.executable, UPDATE_SCRIPT,
         "-i", str(TRAC_TICKET_ID),
         "-f", comment_file,
         "--author", "wwos-triage-cron"],
        capture_output=True, text=True,
    )
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr, file=sys.stderr)
        notify_via_email(
            "Pops -> WWOS triage: FAILED to post to Trac",
            f"{len(candidates)} candidate(s) found but posting to {TRAC_TICKET_URL} failed:\n\n{result.stderr}",
        )
        sys.exit(1)

    email_body = (
        f"{len(candidates)} candidate(s) proposed for Pops -> WWOS graduation this run.\n"
        f"No changes have been made to WWOS or Pops -- this is a proposal only.\n"
        f"Review and approve/reject each candidate in Trac:\n{TRAC_TICKET_URL}\n\n"
        f"{comment}"
    )
    notify_via_email(f"Pops -> WWOS triage: {len(candidates)} candidate(s) awaiting your review", email_body)


if __name__ == "__main__":
    main()
