#!/usr/bin/env python3
"""
================================================================================
Filename:       gnome_sr_ingest.py
Version:        1.0
Author:         OpenCode (jimmy queue worker)
Last Modified:  2026-07-23
Context:        http://trac.home.arpa/ticket/3992

Purpose:
    Phase 2 of the gnome-sound-recorder ingest workflow (Trac #3992):
    automatically discovers new audio recordings in GNOME Sound Recorder's
    data directory on fleet hosts (default: athena, opti-cc76), pulls them to
    a local staging directory, and transcribes each new recording with
    transcribe_audio.py. A JSON state file records which remote files have
    already been processed so only new recordings are pulled on each run.

    Remote recordings directory (all hosts):
        ~/.local/share/org.gnome.SoundRecorder/

    Transcription output lands next to the staged audio file as
    <base>_transcription.txt. Routing transcripts into pops raw/ and
    archiving audio to the Drive data lake (folder
    1oxYokWvdx2BlEsZSF7zBldkdRZCxIy-5) remains the Phase 3 / manual step
    per skills/core/audio-ingest.md.

Prerequisites:
    - SSH access from the executing host to each target host as user 'will'
      (lab key ~/.ssh/id_rsa_lab pre-deployed; see sysadmin-guru SSH Key
      Management). A host matching the local hostname is read directly from
      the filesystem instead of via SSH loopback.
    - python3 on the executing host (stdlib only).
    - transcribe_audio.py (path configurable via --transcribe-script).
    - GEMINI_API_KEY / OPENROUTER_API_KEY are resolved by
      transcribe_audio.py itself (env var or ~/.bashrc).

Secrets:
    None — host authentication uses the pre-deployed SSH lab key
    (~/.ssh/id_rsa_lab); transcription API keys are resolved by
    transcribe_audio.py and never pass through this script.

Usage:
    ./gnome_sr_ingest.py --help
    ./gnome_sr_ingest.py --dry-run                          # list new files only
    ./gnome_sr_ingest.py --hosts athena                     # single host
    ./gnome_sr_ingest.py --context "tcon, eldercare, rnc"   # extra transcription context
    ./gnome_sr_ingest.py --no-transcribe                    # pull only, no transcription

Revision History:
    1.0 (2026-07-23) - Initial version. Trac #3992 (Phase 2: Scripting &
        Extraction). Host enumeration via SSH find, SCP pull, JSON state
        tracking, transcribe_audio.py integration, --dry-run/--no-transcribe
        test modes, localhost filesystem shortcut.

NOTES:
    - Bump the version and annotate the change in Revision History on every
      edit, per WWOS [[Source code headers]].
    - Files younger than --min-age-minutes (default 5) are skipped: they may
      still be open in the recorder.
    - State file default: ~/.local/state/gnome_sr_ingest/state.json
================================================================================
"""

import argparse
import json
import os
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

REMOTE_DIR_DEFAULT = "~/.local/share/org.gnome.SoundRecorder"
AUDIO_EXTS = {".ogg", ".opus", ".m4a", ".mp3", ".flac", ".wav"}
SSH_USER = "will"
SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]


def is_local(host):
    """True if the target host is the machine we are running on."""
    return host in ("localhost", socket.gethostname(), socket.getfqdn())


def list_recordings(host, remote_dir):
    """Return {filename: mtime_epoch} for audio files in remote_dir on host.

    Uses a direct filesystem read for the local host, SSH find otherwise.
    """
    if is_local(host):
        directory = Path(remote_dir).expanduser()
        if not directory.is_dir():
            print(f"  [{host}] directory not found: {directory} (skipping)")
            return {}
        return {
            p.name: p.stat().st_mtime
            for p in directory.iterdir()
            if p.is_file() and p.suffix.lower() in AUDIO_EXTS
        }

    find_cmd = (
        f"find {remote_dir} -maxdepth 1 -type f "
        f"-printf '%f\\t%T@\\n' 2>/dev/null"
    )
    result = subprocess.run(
        ["ssh", *SSH_OPTS, f"{SSH_USER}@{host}", find_cmd],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ssh list failed on {host}: {result.stderr.strip()}")

    recordings = {}
    for line in result.stdout.splitlines():
        name, _, mtime = line.rpartition("\t")
        if name and mtime and Path(name).suffix.lower() in AUDIO_EXTS:
            recordings[name] = float(mtime)
    return recordings


def pull_recording(host, remote_dir, filename, staging_dir):
    """Copy one recording from host into staging_dir. Returns local Path."""
    destination = Path(staging_dir) / filename
    if is_local(host):
        shutil.copy2(Path(remote_dir).expanduser() / filename, destination)
    else:
        remote_path = f"{remote_dir}/{filename}"
        subprocess.run(
            ["scp", *SSH_OPTS,
             f"{SSH_USER}@{host}:{shlex.quote(remote_path)}",
             str(destination)],
            check=True, timeout=600,
        )
    return destination


def transcribe(local_path, transcribe_script, context):
    """Run transcribe_audio.py on a staged file. Returns True on success."""
    cmd = [sys.executable, transcribe_script, str(local_path)]
    if context:
        cmd += ["--context", context]
    result = subprocess.run(cmd, timeout=7200)
    return result.returncode == 0


def load_state(state_path):
    path = Path(state_path).expanduser()
    if path.is_file():
        return json.loads(path.read_text())
    return {}


def save_state(state_path, state):
    path = Path(state_path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp_path.replace(path)


def main():
    parser = argparse.ArgumentParser(
        description="Pull new GNOME Sound Recorder files from fleet hosts "
                    "and transcribe them (Trac #3992 Phase 2).")
    parser.add_argument("--hosts", default="athena,opti-cc76",
                        help="Comma-separated hosts (default: athena,opti-cc76)")
    parser.add_argument("--remote-dir", default=REMOTE_DIR_DEFAULT,
                        help=f"Remote recordings dir (default: {REMOTE_DIR_DEFAULT})")
    parser.add_argument("--staging", default="~/pops/tmp/gnome-sr-ingest",
                        help="Local staging dir (default: ~/pops/tmp/gnome-sr-ingest)")
    parser.add_argument("--state", default="~/.local/state/gnome_sr_ingest/state.json",
                        help="JSON state file path")
    parser.add_argument("--transcribe-script",
                        default="~/ansible-netbox/scripts/transcribe_audio.py",
                        help="Path to transcribe_audio.py")
    parser.add_argument("--context", default="",
                        help="Extra context appended to the transcription prompt")
    parser.add_argument("--min-age-minutes", type=int, default=5,
                        help="Skip files modified within this many minutes "
                             "(default: 5; guards against in-progress recordings)")
    parser.add_argument("--no-transcribe", action="store_true",
                        help="Pull files but skip transcription")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be pulled; change nothing")
    args = parser.parse_args()

    hosts = [h.strip() for h in args.hosts.split(",") if h.strip()]
    staging_dir = Path(args.staging).expanduser()
    transcribe_script = os.path.expanduser(args.transcribe_script)
    state = load_state(args.state)
    now = time.time()
    totals = {"pulled": 0, "transcribed": 0, "skipped": 0, "failed": 0}

    for host in hosts:
        print(f"[{host}] scanning {args.remote_dir} ...")
        try:
            recordings = list_recordings(host, args.remote_dir)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"  ERROR: {exc}")
            totals["failed"] += 1
            continue

        host_state = state.setdefault(host, {})
        for name, mtime in sorted(recordings.items(), key=lambda kv: kv[1]):
            if name in host_state:
                continue
            age_min = (now - mtime) / 60
            if age_min < args.min_age_minutes:
                print(f"  SKIP (too new, {age_min:.1f}m): {name}")
                totals["skipped"] += 1
                continue
            if args.dry_run:
                print(f"  WOULD PULL: {name}")
                continue

            staging_dir.mkdir(parents=True, exist_ok=True)
            print(f"  pulling: {name}")
            try:
                local_path = pull_recording(host, args.remote_dir, name, staging_dir)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                print(f"  ERROR pulling {name}: {exc}")
                totals["failed"] += 1
                continue
            totals["pulled"] += 1

            entry = {"mtime": mtime, "pulled_at": now, "status": "pulled"}
            if not args.no_transcribe:
                context = (
                    f"GNOME Sound Recorder audio captured on host '{host}'. "
                    f"Source filename: {name}. " + args.context
                ).strip()
                print(f"  transcribing: {local_path.name}")
                if transcribe(local_path, transcribe_script, context):
                    entry["status"] = "transcribed"
                    totals["transcribed"] += 1
                else:
                    entry["status"] = "transcribe_failed"
                    totals["failed"] += 1
            host_state[name] = entry
            save_state(args.state, state)

    if args.dry_run:
        print("\nDry run — nothing pulled, state unchanged.")
    else:
        save_state(args.state, state)
        print(f"\nDone. pulled={totals['pulled']} "
              f"transcribed={totals['transcribed']} "
              f"skipped={totals['skipped']} failed={totals['failed']}")
        print(f"Staging: {staging_dir}")
        print("Next (Phase 3, manual per audio-ingest skill): route "
              "*_transcription.txt into pops raw/ and archive audio to the "
              "Drive data lake.")


if __name__ == "__main__":
    main()
