#!/usr/bin/env python3
"""
================================================================================
Filename:       scripts/disk_alert_heartbeat_check.py
Version:        1.0
Author:         jimmy (claude@agent-runner-pve5-01)
Last Modified:  2026-09-03
Context:        http://trac.gafla.us.com/ticket/4494 (WP-5)

Purpose:
    Detect hosts whose disk-alert monitor has stopped reporting.

    check_disk.sh emits one heartbeat per run:
        INFO: disk_alert heartbeat on <host>: N filesystems checked, M breached

    Absence of alerts is otherwise indistinguishable from absence of a
    monitor. That is precisely how pve4 and CT 112 sat unmonitored for weeks
    while the system looked healthy (Trac #4494 F5/F9).

Why this is a script and not a Graylog event definition:
    Graylog aggregation event definitions cannot detect per-host absence.
    An aggregation grouped by `source` only evaluates groups that HAVE
    messages in the window -- when a host goes silent there is no message to
    group on, so the rule never fires for it. An ungrouped `count() == 0`
    rule only catches total fleet silence. Per-host absence therefore has to
    be computed by comparing an expected set against an observed set, which
    is what this does.

Expected-set strategy:
    The expected set is LEARNED from Graylog history rather than read from a
    static list, so it cannot drift out of sync with the inventory. A host is
    "expected" if it produced at least MIN_OBSERVATIONS heartbeats within
    BASELINE_DAYS. A host that has never reported is not expected here --
    catching those is the deployment sweep's job, not this script's.

Usage:
    disk_alert_heartbeat_check.py [--dry-run] [--silent-hours N] [--json]
================================================================================
"""
import os
import sys
import json
import time
import argparse
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scripts import graylog_query as gq  # noqa: E402

HEARTBEAT_QUERY = '"disk_alert heartbeat"'
SILENT_HOURS = 3
BASELINE_DAYS = 7
MIN_OBSERVATIONS = 2
RENOTIFY_HOURS = 24
RECIPIENTS = "root@home.arpa,wrtaff@gmail.com"   # WP-0 decision, Will 2026-09-03
STATE_DIR = os.getenv("HEARTBEAT_STATE_DIR", "/var/lib/disk_alert")
STATE_FILE = os.path.join(STATE_DIR, "heartbeat_absence.state")
TRAC_URL = "http://trac.gafla.us.com/ticket/4494"


def _parse_ts(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def collect(baseline_days=BASELINE_DAYS):
    """Return {source: (last_seen_datetime, observation_count)}."""
    msgs = gq.query_messages(
        query=HEARTBEAT_QUERY,
        hours=baseline_days * 24,
        limit=5000,
        fields=["source", "timestamp", "message"],
    )
    seen = defaultdict(lambda: [None, 0])
    for m in msgs:
        src = m.get("source")
        ts = _parse_ts(m.get("timestamp"))
        if not src or ts is None:
            continue
        entry = seen[src]
        entry[1] += 1
        if entry[0] is None or ts > entry[0]:
            entry[0] = ts
    return {k: tuple(v) for k, v in seen.items()}


def find_silent(seen, silent_hours=SILENT_HOURS):
    now = datetime.now(timezone.utc)
    silent, healthy = [], []
    for src, (last, count) in sorted(seen.items()):
        if count < MIN_OBSERVATIONS:
            continue  # not enough history to call it "expected"
        age_h = (now - last).total_seconds() / 3600.0
        (silent if age_h >= silent_hours else healthy).append((src, last, age_h))
    return silent, healthy


def should_notify():
    """Re-notify at most every RENOTIFY_HOURS while the condition persists."""
    try:
        with open(STATE_FILE) as f:
            last = float(f.read().strip())
    except (OSError, ValueError):
        return True
    return (time.time() - last) >= RENOTIFY_HOURS * 3600


def send(silent, healthy):
    subject = f"CRITICAL: disk-alert monitor silent on {len(silent)} host(s)"
    lines = [
        f"{len(silent)} host(s) have not sent a disk_alert heartbeat in "
        f"{SILENT_HOURS}h. Their disk monitoring is not running, so a full "
        f"filesystem on these hosts would NOT raise an alert.",
        "",
    ]
    for src, last, age in silent:
        lines.append(f"  {src:<28} last heartbeat {age:6.1f}h ago  ({last:%Y-%m-%d %H:%M UTC})")
    lines += ["", f"Still reporting normally: {len(healthy)} host(s).", "",
              f"Ticket: {TRAC_URL}", "",
              "Check on the affected host:  systemctl status disk-alert.timer"]
    body = "\n".join(lines)
    try:
        p = subprocess.run(["mail", "-s", subject, RECIPIENTS],
                           input=body, text=True, timeout=60)
        if p.returncode != 0:
            print(f"heartbeat_check: DELIVERY FAILED rc={p.returncode}", file=sys.stderr)
            return False
    except (OSError, subprocess.SubprocessError) as e:
        print(f"heartbeat_check: DELIVERY FAILED {e}", file=sys.stderr)
        return False
    # State is written ONLY on successful delivery, so a failed send retries
    # rather than being silently latched (same discipline as check_disk.sh).
    try:
        os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            f.write(str(time.time()))
    except OSError as e:
        print(f"heartbeat_check: could not write state: {e}", file=sys.stderr)
    return True


def main():
    ap = argparse.ArgumentParser(description="Alert on disk-alert monitors that have gone silent.")
    ap.add_argument("--dry-run", action="store_true", help="report only, send no mail, write no state")
    ap.add_argument("--silent-hours", type=int, default=SILENT_HOURS)
    ap.add_argument("--baseline-days", type=int, default=BASELINE_DAYS)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    seen = collect(a.baseline_days)
    silent, healthy = find_silent(seen, a.silent_hours)

    if a.json:
        print(json.dumps({
            "silent": [{"source": s, "last_seen": l.isoformat(), "age_hours": round(h, 2)} for s, l, h in silent],
            "healthy": [{"source": s, "age_hours": round(h, 2)} for s, l, h in healthy],
            "baseline_hosts": len(seen),
        }, indent=2))
    else:
        print(f"baseline hosts seen in {a.baseline_days}d: {len(seen)}")
        print(f"reporting normally: {len(healthy)}")
        print(f"SILENT (>= {a.silent_hours}h): {len(silent)}")
        for s, l, h in silent:
            print(f"   {s:<28} {h:6.1f}h ago")

    if not silent:
        # Condition cleared -- drop state so the next occurrence alerts immediately.
        if not a.dry_run:
            try:
                os.remove(STATE_FILE)
            except OSError:
                pass
        return 0
    if a.dry_run:
        print("(dry-run: no mail sent, no state written)")
        return 1
    if should_notify():
        return 0 if send(silent, healthy) else 1
    print("(within re-notify window: no mail sent)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
