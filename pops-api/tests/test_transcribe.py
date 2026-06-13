#!/usr/bin/env python3
"""
================================================================================
Filename:       test_transcribe.py
Version:        1.0
Author:         Claude Code
Last Modified:  2026-06-12
Context:        http://trac.home.arpa/ticket/3596

Purpose:
    Tests for POST /api/transcribe and GET /api/transcribe/{job_id}: covers
    authentication (401/403), extension validation (400), oversize upload (413),
    unknown job (404), happy-path transcript delivery, context passthrough to
    the external script, failure path, and job state file correctness. Stub
    scripts written into pytest tmp_path are used throughout; the real
    transcribe_audio.py is never invoked and the real /home/will/pops is
    never touched.

Secrets:
    None - no credentials or secrets required

Usage:
    cd ~/ansible-netbox/pops-api
    /opt/venvs/gemini_projects/bin/python3 -m pytest tests/test_transcribe.py -v

Revision History:
    1.0 - Initial test coverage (Phase 3 subtask P3.2). Trac #3596.
================================================================================
"""

import json
import sys
import time
from io import BytesIO
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_audio(
    client,
    auth_headers,
    filename="test.mp3",
    content=b"FAKE_AUDIO_DATA",
    context=None,
):
    """POST a multipart audio upload to /api/transcribe."""
    data = {}
    if context is not None:
        data["context"] = context
    return client.post(
        "/api/transcribe",
        files={"file": (filename, BytesIO(content), "audio/mpeg")},
        data=data,
        headers=auth_headers,
    )


def _poll_status(client, auth_headers, job_id, max_attempts=15, delay=0.05):
    """
    Poll GET /api/transcribe/{job_id} until status is terminal (done or
    failed). Returns the final JSON body.

    Under FastAPI's TestClient, BackgroundTasks run synchronously within the
    same request handling cycle, so the job is almost always already in a
    terminal state on the first GET. The loop is kept as a safety net in case
    the ASGI transport scheduling ever defers the background task.
    """
    body = {}
    for _ in range(max_attempts):
        resp = client.get(f"/api/transcribe/{job_id}", headers=auth_headers)
        assert resp.status_code == 200, f"unexpected status poll response: {resp.status_code}"
        body = resp.json()
        if body.get("status") in ("done", "failed"):
            return body
        time.sleep(delay)
    return body  # return last observed body even if still pending


def _configure_script(monkeypatch, script_path):
    """
    Point the transcription service at a stub script and clear the settings
    cache so the next get_settings() call picks up the new env vars.
    """
    from app.config import get_settings

    monkeypatch.setenv("POPS_TRANSCRIBE_SCRIPT", str(script_path))
    monkeypatch.setenv("POPS_TRANSCRIBE_PYTHON", sys.executable)
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Fixtures - stub scripts
# ---------------------------------------------------------------------------


@pytest.fixture
def ok_stub(tmp_path):
    """
    Stub that writes '<stem>.txt' (known content) next to its input and exits
    0. The file is found by _locate_output via the '<stem>.txt' candidate.
    """
    script = tmp_path / "ok_stub.py"
    script.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "upload = Path(sys.argv[1])\n"
        "out = upload.parent / (upload.stem + '.txt')\n"
        "out.write_text('Stub transcript: audio content here.', encoding='utf-8')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    return script


@pytest.fixture
def argv_stub(tmp_path):
    """
    Stub that writes the full subprocess argv (space-joined) into the
    transcript .txt, then exits 0. Used to verify --context passthrough.
    """
    script = tmp_path / "argv_stub.py"
    script.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        "upload = Path(sys.argv[1])\n"
        "out = upload.parent / (upload.stem + '.txt')\n"
        "out.write_text(' '.join(sys.argv), encoding='utf-8')\n"
        "sys.exit(0)\n",
        encoding="utf-8",
    )
    return script


@pytest.fixture
def fail_stub(tmp_path):
    """
    Stub that writes a known error message to stderr and exits 1. Used to
    exercise the failure path.
    """
    script = tmp_path / "fail_stub.py"
    script.write_text(
        "import sys\n"
        "sys.stderr.write('audio decode error: codec not found')\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    return script


# ---------------------------------------------------------------------------
# 1. Authentication
# ---------------------------------------------------------------------------


def test_post_transcribe_no_auth_401(client):
    """POST without X-API-Key returns 401."""
    resp = client.post(
        "/api/transcribe",
        files={"file": ("test.mp3", BytesIO(b"data"), "audio/mpeg")},
    )
    assert resp.status_code == 401


def test_post_transcribe_wrong_key_403(client):
    """POST with wrong X-API-Key returns 403."""
    resp = client.post(
        "/api/transcribe",
        files={"file": ("test.mp3", BytesIO(b"data"), "audio/mpeg")},
        headers={"X-API-Key": "not-the-right-key"},
    )
    assert resp.status_code == 403


def test_get_transcribe_no_auth_401(client):
    """GET job status without X-API-Key returns 401."""
    resp = client.get("/api/transcribe/somejobid")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# 2. Validation
# ---------------------------------------------------------------------------


def test_disallowed_extension_400(client, auth_headers):
    """
    Uploading a .exe file is rejected with 400. The detail message must mention
    the rejected extension and list the allowed extensions.
    """
    resp = _post_audio(client, auth_headers, filename="payload.exe")
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    # Detail should reference the bad extension and at least one allowed ext.
    assert ".exe" in detail or "unsupported" in detail.lower()
    assert ".mp3" in detail or "allowed" in detail.lower()


def test_oversize_upload_413_staged_file_removed(
    client, auth_headers, monkeypatch, temp_pops_root
):
    """
    An upload that exceeds POPS_UPLOAD_MAX_BYTES returns 413 and the partial
    staged file is removed from uploads_dir (not left as orphaned debris).
    """
    from app.config import get_settings

    monkeypatch.setenv("POPS_UPLOAD_MAX_BYTES", "10")
    get_settings.cache_clear()

    # 100 bytes >> 10-byte cap; upload will be chunked, cap hit, file unlinked.
    resp = _post_audio(client, auth_headers, content=b"X" * 100)
    assert resp.status_code == 413

    uploads_dir = temp_pops_root / "tmp" / "api-uploads"
    if uploads_dir.exists():
        remaining = list(uploads_dir.iterdir())
        assert remaining == [], (
            f"partial staged file was not removed after 413: {remaining}"
        )


# ---------------------------------------------------------------------------
# 3. Unknown job 404
# ---------------------------------------------------------------------------


def test_get_unknown_job_404(client, auth_headers):
    """GET /api/transcribe/<nonexistent-id> returns 404."""
    resp = client.get("/api/transcribe/doesnotexist", headers=auth_headers)
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 4. Happy path
# ---------------------------------------------------------------------------


def test_happy_path_202_and_done(
    client, auth_headers, monkeypatch, temp_pops_root, ok_stub
):
    """
    POST a small fake .mp3 with an ok stub script:
    - Returns 202 with job_id and status_url.
    - GET eventually shows status "done" (TestClient runs BackgroundTasks
      synchronously, so it is done on the first poll).
    - transcript_text matches the stub's known output.
    - transcript_path is under raw/transcripts/ inside the temp root and the
      file exists on disk.
    - Staged upload in uploads_dir is removed.
    - original_filename is preserved in the status response.
    """
    _configure_script(monkeypatch, ok_stub)

    resp = _post_audio(client, auth_headers, filename="memo.mp3")
    assert resp.status_code == 202

    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "pending"
    job_id = body["job_id"]
    assert body["status_url"] == f"/api/transcribe/{job_id}"

    status = _poll_status(client, auth_headers, job_id)
    assert status["status"] == "done", f"expected done, got full status: {status}"

    # original_filename preserved.
    assert status["original_filename"] == "memo.mp3"

    # Transcript text matches stub output exactly.
    assert status.get("transcript_text") == "Stub transcript: audio content here."

    # transcript_path is under raw/transcripts/ in the temp tree and exists.
    transcript_path = Path(status["transcript_path"])
    assert transcript_path.parent == temp_pops_root / "raw" / "transcripts"
    assert transcript_path.exists(), f"transcript file missing: {transcript_path}"

    # Staged upload must have been cleaned up on success.
    uploads_dir = temp_pops_root / "tmp" / "api-uploads"
    if uploads_dir.exists():
        mp3_files = list(uploads_dir.glob("*.mp3"))
        assert mp3_files == [], f"staged upload not removed: {mp3_files}"


# ---------------------------------------------------------------------------
# 5. Context passthrough
# ---------------------------------------------------------------------------


def test_context_passthrough_to_script(
    client, auth_headers, monkeypatch, argv_stub
):
    """
    When the context form field is supplied, --context <value> is passed to
    the transcription script. The argv_stub echoes sys.argv into the
    transcript, so both the flag name and the value must appear there.
    """
    _configure_script(monkeypatch, argv_stub)

    resp = _post_audio(
        client, auth_headers, filename="meeting.mp3", context="board meeting"
    )
    assert resp.status_code == 202

    job_id = resp.json()["job_id"]
    status = _poll_status(client, auth_headers, job_id)
    assert status["status"] == "done", f"expected done, got: {status}"

    transcript = status.get("transcript_text") or ""
    assert "--context" in transcript, (
        f"--context flag not found in transcript: {transcript!r}"
    )
    assert "board meeting" in transcript, (
        f"context value not found in transcript: {transcript!r}"
    )


# ---------------------------------------------------------------------------
# 6. Failure path
# ---------------------------------------------------------------------------


def test_failure_path_failed_status_and_upload_retained(
    client, auth_headers, monkeypatch, temp_pops_root, fail_stub
):
    """
    When the script exits 1 with a stderr message:
    - Job status is "failed".
    - error field contains the stderr snippet.
    - transcript_text is absent or null (never present on failure).
    - Staged upload is RETAINED in uploads_dir for post-mortem debugging.
    """
    _configure_script(monkeypatch, fail_stub)

    resp = _post_audio(client, auth_headers, filename="bad_audio.mp3")
    assert resp.status_code == 202

    job_id = resp.json()["job_id"]
    status = _poll_status(client, auth_headers, job_id)
    assert status["status"] == "failed", f"expected failed, got: {status}"

    # Error field should contain the known stderr snippet.
    error = status.get("error") or ""
    assert "audio decode error" in error or "codec" in error, (
        f"stderr snippet not found in error field: {error!r}"
    )

    # transcript_text must be absent or None on a failed job.
    assert status.get("transcript_text") is None, (
        f"transcript_text should be absent on failure, got: {status.get('transcript_text')!r}"
    )

    # Staged upload is kept (not deleted) so the operator can inspect it.
    uploads_dir = temp_pops_root / "tmp" / "api-uploads"
    mp3_files = list(uploads_dir.glob("*.mp3")) if uploads_dir.exists() else []
    assert mp3_files, (
        "staged upload should be retained in uploads_dir after a failure, but none found"
    )


# ---------------------------------------------------------------------------
# 7. Job state file
# ---------------------------------------------------------------------------


def test_job_state_file_has_documented_fields(
    client, auth_headers, monkeypatch, temp_pops_root, ok_stub
):
    """
    After a happy-path run, jobs_dir/<job_id>.json exists and parses as valid
    JSON with all documented fields. Field values are spot-checked for
    correctness (status "done", original_filename, non-null timestamps, etc.).
    """
    _configure_script(monkeypatch, ok_stub)

    resp = _post_audio(client, auth_headers, filename="notes.mp3")
    assert resp.status_code == 202
    job_id = resp.json()["job_id"]

    # Ensure background task has finished before inspecting the file.
    final = _poll_status(client, auth_headers, job_id)
    assert final["status"] == "done", f"job did not reach done state: {final}"

    jobs_dir = temp_pops_root / "tmp" / "api-jobs"
    job_file = jobs_dir / f"{job_id}.json"
    assert job_file.exists(), f"job state file not found at expected path: {job_file}"

    with open(job_file, "r", encoding="utf-8") as fh:
        job_data = json.load(fh)

    # All documented fields must be present.
    required_fields = (
        "job_id",
        "status",
        "original_filename",
        "upload_path",
        "context",
        "created",
        "started",
        "finished",
        "transcript_path",
        "error",
    )
    for field in required_fields:
        assert field in job_data, f"missing field in job JSON: {field!r}"

    # Spot-check values.
    assert job_data["job_id"] == job_id
    assert job_data["status"] == "done"
    assert job_data["original_filename"] == "notes.mp3"
    assert job_data["started"] is not None, "started should be set after run"
    assert job_data["finished"] is not None, "finished should be set after success"
    assert job_data["transcript_path"] is not None, "transcript_path should be recorded"
    assert job_data["error"] is None, "error should be null on success"
