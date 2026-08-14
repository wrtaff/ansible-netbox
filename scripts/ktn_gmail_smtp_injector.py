#!/usr/bin/env python3
"""Inject Gmail messages into a local Kill the Newsletter SMTP receiver.

The process uses a Gmail OAuth token with gmail.modify scope, fetches messages
under one configured label, submits each raw RFC 2822 message to the matching
KTN feed address, and removes the label only after SMTP accepts the message.
Credentials and label-to-feed mappings are supplied by the deployment layer.
"""

import argparse
import base64
import json
import logging
import smtplib
import socket

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
LOG = logging.getLogger("ktn-gmail-smtp-injector")


def load_credentials(token_file):
    with open(token_file, encoding="utf-8") as stream:
        credentials = Credentials.from_authorized_user_info(json.load(stream), [GMAIL_SCOPE])
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials.valid:
        raise RuntimeError("Gmail OAuth credentials are invalid or expired")
    return credentials


def label_id(service, label_name):
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for label in labels:
        if label.get("name") == label_name:
            return label["id"]
    raise RuntimeError(f"Gmail label not found: {label_name}")


def message_ids(service, label_name, limit):
    response = service.users().messages().list(
        userId="me", q=f'label:"{label_name}"', maxResults=limit
    ).execute()
    return [message["id"] for message in response.get("messages", [])]


def raw_message(service, message_id):
    message = service.users().messages().get(
        userId="me", id=message_id, format="raw"
    ).execute()
    return base64.urlsafe_b64decode(message["raw"] + "===")


def relay(raw, recipient, smtp_host, smtp_port, sender):
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as client:
        client.sendmail(sender, [recipient], raw)


def process(service, label_name, recipient, args):
    label = label_id(service, label_name)
    ids = message_ids(service, label_name, args.max_messages)
    for message_id in ids:
        raw = raw_message(service, message_id)
        if args.dry_run:
            LOG.info("dry-run message=%s label=%s bytes=%d", message_id, label_name, len(raw))
            continue
        relay(raw, recipient, args.smtp_host, args.smtp_port, args.envelope_sender)
        service.users().messages().modify(
            userId="me", id=message_id, body={"removeLabelIds": [label]}
        ).execute()
        LOG.info("relayed message=%s label=%s recipient=%s", message_id, label_name, recipient)
    return len(ids)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--smtp-host", default="127.0.0.1")
    parser.add_argument("--smtp-port", type=int, default=2525)
    parser.add_argument("--envelope-sender", default=f"ktn-injector@{socket.getfqdn()}")
    parser.add_argument("--max-messages", type=int, default=20)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    credentials = load_credentials(args.token_file)
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    process(service, args.label, args.recipient, args)


if __name__ == "__main__":
    main()
