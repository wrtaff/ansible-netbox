#!/usr/bin/env python3
"""
================================================================================
Filename:       transcribe_jobs.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3596

Purpose:
    Background-job service backing the /api/transcribe endpoint of the Pops KMS
    REST API. A job is a single JSON file under settings.jobs_dir tracking the
    lifecycle of one audio-transcription request (pending -> running ->
    done/failed). run_job invokes the external transcribe_audio.py script in a
    subprocess (intended for FastAPI BackgroundTasks), then files the resulting
    transcript under settings.transcripts_dir. All filesystem and subprocess
    logic lives here so the router stays thin.

Secrets:
    None held by this module - GEMINI_API_KEY / OPENROUTER_API_KEY are resolved
    internally by transcribe_audio.py (env var or ~/.bashrc); never logged here.

Usage:
    from app.services.transcribe_jobs import (
        ALLOWED_EXTENSIONS, create_job, run_job, get_job, read_transcript,
    )
    job = create_job(upload_path, "memo.mp3", context="board meeting")
    run_job(job["job_id"])          # blocking; run via BackgroundTasks
    job = get_job(job_id)
    text = read_transcript(job)

Revision History:
    1.0 - Initial implementation (Phase 3 subtask P3.1). Trac #3596.
================================================================================
"""

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.config import get_settings

# Audio/video container extensions transcribe_audio.py is expected to handle.
ALLOWED_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".mp4",
    ".wav",
    ".ogg",
    ".flac",
    ".aac",
    ".webm",
    ".mov",
}

# Cap on the stderr snippet stored in a failed job's error field.
_ERROR_SNIPPET_MAX = 300


def _now_iso() -> str:
    """Current UTC time as an ISO 8601 'Z' string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _job_path(job_id: str) -> Path:
    """Filesystem path of the JSON state file for a job."""
    return get_settings().jobs_dir / f"{job_id}.json"


def _write_job(job: dict) -> None:
    """Atomically write a job's JSON state file (tmp file + os.replace)."""
    path = _job_path(job["job_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(job, fh, indent=2)
    os.replace(tmp, path)


def create_job(upload_path: Path, original_filename: str, context: str | None) -> dict:
    """
    Create a pending transcription job and persist its JSON state file.

    Args:
        upload_path:       Path to the already-staged upload on disk.
        original_filename: Client-supplied filename (used for the transcript
                           name and reported back to the client).
        context:           Optional context string passed to the script.

    Returns:
        The job dict (status "pending").
    """
    job_id = uuid4().hex
    job = {
        "job_id": job_id,
        "status": "pending",
        "original_filename": original_filename,
        "upload_path": str(upload_path),
        "context": context,
        "created": _now_iso(),
        "started": None,
        "finished": None,
        "transcript_path": None,
        "error": None,
    }
    _write_job(job)
    return job


def get_job(job_id: str) -> dict | None:
    """Return the job dict for job_id, or None if no such job file exists."""
    path = _job_path(job_id)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _locate_output(upload_path: Path) -> Path | None:
    """
    Find the transcript .txt that transcribe_audio.py wrote next to its input.

    The real script writes '<stem>_transcription.txt'; a test stub may write
    '<stem>.txt'. Check both explicit names, then fall back to a glob so any
    '<stem>*.txt' sibling is found.
    """
    parent = upload_path.parent
    stem = upload_path.stem
    candidates = [
        parent / f"{stem}_transcription.txt",
        parent / f"{stem}.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    matches = sorted(parent.glob(f"{stem}*.txt"))
    return matches[0] if matches else None


def run_job(job_id: str) -> None:
    """
    Execute a transcription job. Intended to run via FastAPI BackgroundTasks.

    Marks the job running, invokes the configured transcription script on the
    staged upload, and on success moves the produced transcript into
    settings.transcripts_dir and deletes the staged upload. Any failure
    (nonzero exit, timeout, missing output, unexpected exception) marks the job
    failed with a short, secret-free error snippet and KEEPS the staged upload
    for debugging. Exceptions are fully contained so a background failure can
    never crash the server.
    """
    job = get_job(job_id)
    if job is None:
        return

    settings = get_settings()
    upload_path = Path(job["upload_path"])

    job["status"] = "running"
    job["started"] = _now_iso()
    _write_job(job)

    try:
        cmd = [
            settings.transcribe_python,
            settings.transcribe_script,
            str(upload_path),
        ]
        if job.get("context"):
            cmd += ["--context", job["context"]]

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=settings.transcribe_timeout,
        )

        if proc.returncode != 0:
            snippet = (proc.stderr or proc.stdout or "transcription failed").strip()
            _fail(job, f"script exited {proc.returncode}: {snippet}")
            return

        output = _locate_output(upload_path)
        if output is None:
            _fail(job, "transcription finished but no output .txt was found")
            return

        transcripts_dir = settings.transcripts_dir
        transcripts_dir.mkdir(parents=True, exist_ok=True)
        original_stem = Path(job["original_filename"]).stem
        dest = transcripts_dir / f"{original_stem}-{job_id[:8]}.txt"
        os.replace(output, dest)

        # Success: drop the staged upload, record the transcript location.
        try:
            upload_path.unlink()
        except OSError:
            pass

        job["status"] = "done"
        job["transcript_path"] = str(dest)
        job["finished"] = _now_iso()
        job["error"] = None
        _write_job(job)
    except subprocess.TimeoutExpired:
        _fail(job, f"transcription timed out after {settings.transcribe_timeout}s")
    except Exception as exc:  # never let a background failure kill the server
        _fail(job, f"unexpected error: {exc}")


def _fail(job: dict, message: str) -> None:
    """Mark a job failed with a truncated, secret-free error message."""
    job["status"] = "failed"
    job["finished"] = _now_iso()
    job["error"] = message[:_ERROR_SNIPPET_MAX]
    _write_job(job)


def read_transcript(job: dict) -> str | None:
    """
    Return the full transcript text for a completed job, else None.

    Returns None when the job is not done, has no recorded transcript_path, or
    the file cannot be read.
    """
    if job.get("status") != "done":
        return None
    path = job.get("transcript_path")
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None
