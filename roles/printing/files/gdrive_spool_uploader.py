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
    parser.add_argument("--alert-email", default="wrtaff@gmail.com")
    parser.add_argument("--alert-hosts", default="limbo-f0.home.arpa,athena.home.arpa")
    parser.add_argument("--notify-key", default="/etc/gdrive-uploader/notify_key")
    return parser.parse_args()


def send_email_alert(recipient, subject, body):
    """Send email alert via local postfix relay."""
    if not recipient:
        return
    try:
        from email.message import EmailMessage
        import smtplib
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = "cups-print-server@home.arpa"
        msg["To"] = recipient
        msg.set_content(body)

        with smtplib.SMTP("localhost", 25, timeout=10) as client:
            client.send_message(msg)
        logging.info("Sent alert email to %s", recipient)
    except Exception as err:
        logging.error("Failed to send alert email to %s: %s", recipient, err)


def send_desktop_notification(hosts_str, key_path, title, message):
    """Send critical desktop notification popup via SSH to active user sessions."""
    if not hosts_str or not key_path or not os.path.exists(key_path):
        if key_path and not os.path.exists(key_path):
            logging.warning("Notify key %s does not exist, skipping desktop alert", key_path)
        return

    import shlex
    import subprocess

    hosts = [h.strip() for h in hosts_str.split(",") if h.strip()]
    known_hosts_path = "/etc/gdrive-uploader/known_hosts"
    known_hosts_opt = ["-o", f"UserKnownHostsFile={known_hosts_path}"] if os.path.exists(known_hosts_path) else []

    for host in hosts:
        try:
            remote_cmd = (
                f"DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus "
                f"notify-send -u critical -i dialog-error "
                f"{shlex.quote(title)} {shlex.quote(message)}"
            )
            ssh_cmd = [
                "ssh",
                "-i", key_path,
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes",
                "-o", "ConnectTimeout=3"
            ] + known_hosts_opt + [f"will@{host}", remote_cmd]
            subprocess.run(ssh_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
            logging.info("Dispatched desktop notification to %s", host)
        except Exception as err:
            logging.warning("Failed to send desktop notification to %s: %s", host, err)



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
    with open(credentials_path, "r") as handle:
        data = json.load(handle)
    if "type" in data and data["type"] == "service_account":
        credentials = service_account.Credentials.from_service_account_info(data, scopes=SCOPES)
    else:
        from google.oauth2.credentials import Credentials
        credentials = Credentials.from_authorized_user_info(data, scopes=SCOPES)
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def upload(service, source, folder_id):
    media = MediaFileUpload(str(source), mimetype="application/pdf", resumable=True)
    return service.files().create(
        body={"name": source.name, "parents": [folder_id]},
        media_body=media,
        fields="id,name",
        supportsAllDrives=True,
    ).execute()


def process_file(source, processing_dir, completed_dir, quarantine_dir, state_dir, service, folder_id, alert_email=None, alert_hosts=None, notify_key=None):
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
        return False
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
            return False

        state["failure_class"] = "transient-exhausted" if transient else "permanent"
        write_state(state_file, state)
        os.replace(processing, quarantine_dir / processing.name)
        logging.error("quarantined %s: %s", processing.name, error)

        # Dispatch immediate multi-channel notifications
        doc_name = processing.name
        error_msg = str(error)
        time_str = time.strftime("%Y-%m-%d %H:%M:%S %Z", time.localtime())

        # 1. Desktop Notification
        desktop_title = "Google Drive Print FAILED"
        desktop_body = f"Document: {doc_name}\nError: {error_msg}\nStatus: Moved to spool quarantine on cups-lxc"
        send_desktop_notification(alert_hosts, notify_key, desktop_title, desktop_body)

        # 2. Email Notification
        email_subject = f"[CUPS Print Alert] Google Drive Upload Failed: {doc_name}"
        email_body = f"""CUPS Google Drive Print Alert
=============================
A print job spooled to Print_to_Google_Drive failed to upload and has been quarantined.

Document:  {doc_name}
Timestamp: {time_str}
Printer:   Print_to_Google_Drive (cups.home.arpa)
Error:     {error_msg}
Spool:     {quarantine_dir / doc_name}

Action Required:
1. Verify Google Workspace credentials on controller athena.
2. Resync credentials to cups-lxc:/etc/gdrive-uploader/service-account.json.
3. Move the document from quarantine back into incoming to retry:
   mv {quarantine_dir / doc_name} {processing_dir.parent / "incoming" / doc_name}
"""
        send_email_alert(alert_email, email_subject, email_body)
        return True


def main():
    args = parse_args()
    root = Path(args.spool_root)
    directories = {name: root / name for name in ("incoming", "processing", "completed", "quarantine", "state")}
    for directory in directories.values():
        if not directory.is_dir():
            raise SystemExit(f"missing spool directory: {directory}")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    service = drive_service(args.credentials)
    quarantined_any = False
    for source in sorted(directories["incoming"].glob("*.pdf")):
        if process_file(
            source,
            directories["processing"],
            directories["completed"],
            directories["quarantine"],
            directories["state"],
            service,
            args.folder_id,
            alert_email=args.alert_email,
            alert_hosts=args.alert_hosts,
            notify_key=args.notify_key,
        ):
            quarantined_any = True

    if quarantined_any:
        logging.error("Finished spool run with quarantined print jobs.")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        logging.exception("gdrive spool uploader stopped: %s", error)
        sys.exit(1)
