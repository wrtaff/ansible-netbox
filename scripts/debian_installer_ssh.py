#!/usr/bin/env python3
"""
================================================================================
Filename:       debian_installer_ssh.py
Version:        1.0
Author:         OpenCode
Last Modified:  2026-08-08
Context:        http://trac.gafla.us.com/ticket/4173

Purpose:
    Keep one raw-terminal SSH session attached to a Debian Installer
    network-console. This preserves installer state across agent interactions
    and forwards navigation keys without printing literal escape sequences.

Secrets:
    INSTALLER_PASSWORD  (environment variable set by the invoking terminal) -
                       temporary Debian Installer network-console password.
                       If absent, the script prompts without echoing input.

Usage:
    python3 debian_installer_ssh.py installer@192.168.0.95
    INSTALLER_PASSWORD=<temporary-value> python3 debian_installer_ssh.py installer@HOST

Revision History:
    1.0 - Initial raw-PTY Debian Installer SSH bridge. Trac #4173.

Notes:
    Bump Version and add a Revision History entry for every change.
================================================================================
"""

import argparse
import getpass
import os
import pty
import select
import sys
import termios
import tty


def parse_target(value: str) -> tuple[str, str]:
    if "@" not in value:
        raise argparse.ArgumentTypeError("target must be USER@HOST")
    user, host = value.split("@", 1)
    if not user or not host:
        raise argparse.ArgumentTypeError("target must be USER@HOST")
    return user, host


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Attach one raw-PTY SSH session to Debian Installer network-console."
    )
    parser.add_argument("target", type=parse_target, help="installer account and host")
    parser.add_argument(
        "--password-env",
        default="INSTALLER_PASSWORD",
        help="environment variable holding the temporary installer password",
    )
    parser.add_argument(
        "--strict-host-key-checking",
        default="accept-new",
        choices=("yes", "accept-new", "no"),
        help="SSH host-key policy (default: accept-new)",
    )
    args = parser.parse_args()
    user, host = args.target

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        parser.error("requires an interactive terminal; run inside tmux for persistence")

    password = os.environ.get(args.password_env)
    if password is None:
        password = getpass.getpass("Debian Installer network-console password: ")

    pid, master = pty.fork()
    if pid == 0:
        os.execvp(
            "ssh",
            [
                "ssh",
                "-tt",
                "-o",
                "PreferredAuthentications=password",
                "-o",
                "PubkeyAuthentication=no",
                "-o",
                f"StrictHostKeyChecking={args.strict_host_key_checking}",
                "-o",
                "ConnectTimeout=10",
                f"{user}@{host}",
            ],
        )

    stdin_fd = sys.stdin.fileno()
    saved_tty = termios.tcgetattr(stdin_fd)
    password_sent = False
    tty.setraw(stdin_fd)
    try:
        while True:
            readable, _, _ = select.select([master, stdin_fd], [], [])
            if master in readable:
                try:
                    data = os.read(master, 8192)
                except OSError:
                    break
                if not data:
                    break
                if not password_sent and b"assword" in data.lower():
                    os.write(master, password.encode() + b"\n")
                    password_sent = True
                os.write(sys.stdout.fileno(), data)
            if stdin_fd in readable:
                data = os.read(stdin_fd, 8192)
                if not data:
                    break
                os.write(master, data)
    finally:
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, saved_tty)

    _, status = os.waitpid(pid, 0)
    return os.waitstatus_to_exitcode(status)


if __name__ == "__main__":
    raise SystemExit(main())
