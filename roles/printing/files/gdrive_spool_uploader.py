#!/usr/bin/env python3
"""Upload completed CUPS PDFs from a durable spool to Google Drive."""

import argparse
import hashlib
import json
import logging
import os
import random
import sys
import time
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload


RETRY_DELAYS = (60, 300, 900, 3600, 14400)
SCOPES = ("https://www.googleapis.com/auth/drive.file",)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spool-root", required=True)
    parser.add_argument("--folder-id", required=True)
    parser.add_argument("--credentials", required=True)
    return parser.parse_args()


def state_path(state_dir, file_path):
    return state_dir / f"{file_path.name}.json"


def load_state(path):
    if not path.exists():
        return {"attempts": 0}
    with path.open() as handle:
        return json.load(handle)


def write_state(path, state):
    temporary = path.with_suffix(".tmp")
    with temporary.open("w") as handle:
        json.dump(state, handle, sort_keys=True)
    os.replace(temporary, path)


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_transient(error):
    if isinstance(error, HttpError):
        return error.resp.status in (408, 429) or error.resp.status >= 500
    return isinstance(error, (ConnectionError, TimeoutError, OSError))


def drive_service(credentials_path):
    credentials = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=SCOPES
    )
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def upload(service, source, folder_id):
    media = MediaFileUpload(str(source), mimetype="application/pdf", resumable=True)
    return service.files().create(
        body={"name": source.name, "parents": [folder_id]},
        media_body=media,
        fields="id,name",
        supportsAllDrives=True,
    ).execute()


def process_file(source, processing_dir, completed_dir, quarantine_dir, state_dir, service, folder_id):
    processing = processing_dir / source.name
    os.replace(source, processing)
    state_file = state_path(state_dir, processing)
    state = load_state(state_file)

    try:
        if processing.suffix.lower() != ".pdf":
            raise ValueError("spool file is not a PDF")
        result = upload(service, processing, folder_id)
        state.update({
            "drive_file_id": result["id"],
            "uploaded_at": int(time.time()),
            "sha256": checksum(processing),
        })
        write_state(state_file, state)
        os.replace(processing, completed_dir / processing.name)
        logging.info("uploaded %s as Drive file %s", processing.name, result["id"])
        return
    except Exception as error:
        state["attempts"] = state.get("attempts", 0) + 1
        state["last_error"] = str(error)
        state["last_failure_at"] = int(time.time())
        transient = is_transient(error)
        if transient and state["attempts"] <= len(RETRY_DELAYS):
            delay = RETRY_DELAYS[state["attempts"] - 1] + random.randint(0, 30)
            state["next_retry_at"] = int(time.time()) + delay
            write_state(state_file, state)
            logging.warning("retrying %s after %ss: %s", processing.name, delay, error)
            time.sleep(delay)
            os.replace(processing, source)
            return

        state["failure_class"] = "transient-exhausted" if transient else "permanent"
        write_state(state_file, state)
        os.replace(processing, quarantine_dir / processing.name)
        logging.error("quarantined %s: %s", processing.name, error)


def main():
    args = parse_args()
    root = Path(args.spool_root)
    directories = {name: root / name for name in ("incoming", "processing", "completed", "quarantine", "state")}
    for directory in directories.values():
        if not directory.is_dir():
            raise SystemExit(f"missing spool directory: {directory}")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    service = drive_service(args.credentials)
    for source in sorted(directories["incoming"].glob("*.pdf")):
        process_file(
            source,
            directories["processing"],
            directories["completed"],
            directories["quarantine"],
            directories["state"],
            service,
            args.folder_id,
        )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        logging.exception("gdrive spool uploader stopped: %s", error)
        sys.exit(1)
