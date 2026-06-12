#!/usr/bin/env python3
"""
================================================================================
Filename:       transcribe.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3596

Purpose:
    Audio-transcription endpoints for the Pops KMS REST API, using a background
    job pattern. POST /api/transcribe accepts an uploaded audio file (and an
    optional context string), streams it to disk under a size cap, registers a
    pending job, schedules the transcription to run in the background, and
    returns HTTP 202 with a status URL. GET /api/transcribe/{job_id} reports the
    job's status and, once done, the full transcript text. The router stays
    thin: all filesystem and subprocess logic lives in
    app.services.transcribe_jobs.

Secrets:
    None - the transcription script resolves its own API keys internally.

Usage:
    POST /api/transcribe
    Headers: X-API-Key: <key>
    Body (multipart/form-data): file=<audio>, context=<optional text>
    Success: HTTP 202 {"job_id": "...", "status": "pending",
                       "status_url": "/api/transcribe/<job_id>"}
    Errors:
        400  file extension not in the allowed list
        401  X-API-Key header missing
        403  X-API-Key header value invalid
        413  upload exceeds POPS_UPLOAD_MAX_BYTES

    GET /api/transcribe/{job_id}
    Headers: X-API-Key: <key>
    Success: HTTP 200 {job_id, status, original_filename, created, started,
                       finished, transcript_path, error[, transcript_text]}
    Errors:
        401/403  auth as above
        404      no such job

Revision History:
    1.0 - Initial implementation (Phase 3 subtask P3.1). Trac #3596.
================================================================================
"""

from pathlib import Path
from typing import Optional
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)

from app.auth import require_api_key
from app.config import get_settings
from app.services.transcribe_jobs import (
    ALLOWED_EXTENSIONS,
    create_job,
    get_job,
    read_transcript,
    run_job,
)

router = APIRouter(dependencies=[Depends(require_api_key)], tags=["transcription"])

_CHUNK_SIZE = 1024 * 1024  # 1 MiB


@router.post("/transcribe", status_code=202)
async def post_transcribe(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    context: Optional[str] = Form(None),
) -> dict:
    """
    Accept an audio upload, stage it to disk, and schedule a background
    transcription job. Returns HTTP 202 with the job id and status URL.
    """
    settings = get_settings()

    original_filename = file.filename or "upload"
    ext = Path(original_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(
            status_code=400,
            detail=f"unsupported file extension '{ext}'; allowed: {allowed}",
        )

    job_prefix = uuid4().hex
    uploads_dir = settings.uploads_dir
    uploads_dir.mkdir(parents=True, exist_ok=True)
    upload_path = uploads_dir / f"{job_prefix}_{Path(original_filename).name}"

    total = 0
    try:
        with open(upload_path, "wb") as fh:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.upload_max_bytes:
                    fh.close()
                    upload_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            "upload exceeds maximum size of "
                            f"{settings.upload_max_bytes} bytes"
                        ),
                    )
                fh.write(chunk)
    except HTTPException:
        raise
    finally:
        await file.close()

    job = create_job(upload_path, original_filename, context)
    background_tasks.add_task(run_job, job["job_id"])

    return {
        "job_id": job["job_id"],
        "status": "pending",
        "status_url": f"/api/transcribe/{job['job_id']}",
    }


@router.get("/transcribe/{job_id}")
def get_transcribe(job_id: str) -> dict:
    """
    Report the status of a transcription job. Includes the full transcript text
    once the job has completed. Returns HTTP 404 for an unknown job id.
    """
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    response = {
        "job_id": job["job_id"],
        "status": job["status"],
        "original_filename": job["original_filename"],
        "created": job["created"],
        "started": job["started"],
        "finished": job["finished"],
        "transcript_path": job["transcript_path"],
        "error": job["error"],
    }
    if job["status"] == "done":
        response["transcript_text"] = read_transcript(job)

    return response
