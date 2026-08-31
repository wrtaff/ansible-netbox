#!/usr/bin/env bash
# ==============================================================================
# Filename:       scripts/jimmy_queue_sweep.sh
# Version:        1.0
# Last Modified:  2026-08-30
# Context:        http://trac.gafla.us.com/ticket/4447 (WP-6), #3953, #3892
#
# Purpose:
#    Scheduled, unattended sweep of the Jimmy Trac work queue (owner=jimmy).
#    Jimmy's queue workflow was fully specified in skills/domain/jimmy.md but
#    nothing ever triggered it, so assigned work sat untouched -- a critical
#    eldercare ticket (#1454) sat 18+ days. This is that trigger.
#
#    TRIAGE ONLY. This run classifies tickets and hands anything needing a
#    decision back to Will (owner=will), which now emails him (see #4447 WP-1).
#    It performs no file edits, no shell work, no deployments, and no email.
#
# Guardrails:
#    - Email tools are NOT in the allowlist, so "Zero Autonomous Send" is
#      enforced by the harness, not merely by convention.
#    - No Bash/Write/Edit tools: the run cannot change anything but Trac comments
#      and the owner field.
#    - Kill switch: touch $DISABLE_FLAG to stop all future runs immediately.
#    - flock prevents overlapping runs.
#    - Hard timeout bounds cost and hang risk.
#
# Usage:
#    scripts/jimmy_queue_sweep.sh            # normal (cron) run
#    scripts/jimmy_queue_sweep.sh --dry-run  # print the invocation, run nothing
# ==============================================================================
set -uo pipefail

POPS_DIR="${POPS_DIR:-/home/will/pops}"
LOG="${JIMMY_SWEEP_LOG:-/home/will/ansible-netbox/logs/jimmy_queue_sweep.log}"
LOCK="/tmp/jimmy_queue_sweep.lock"
DISABLE_FLAG="${JIMMY_SWEEP_DISABLE:-/home/will/.jimmy-queue-disabled}"
RUN_TIMEOUT="${JIMMY_SWEEP_TIMEOUT:-900}"
MAX_TICKETS="${JIMMY_SWEEP_MAX_TICKETS:-3}"

log() { printf '%s | %s\n' "$(date -Is)" "$*" >> "$LOG"; }

mkdir -p "$(dirname "$LOG")"

# --- kill switch -------------------------------------------------------------
if [ -e "$DISABLE_FLAG" ]; then
    log "SKIP: kill switch present ($DISABLE_FLAG)"
    exit 0
fi

# --- tools the run is permitted to use ---------------------------------------
# Anything absent from this list is denied in --print mode. Gmail/Workspace,
# Bash, Write and Edit are deliberately absent.
ALLOWED="mcp__trac__trac_ping mcp__trac__trac_search_tickets mcp__trac__trac_get_ticket mcp__trac__trac_update_ticket Read Grep Glob"
# Belt and braces: named explicitly so widening ALLOWED later cannot silently
# re-enable autonomous sending.
DISALLOWED="Bash Write Edit mcp__google-workspace__gmail_send_message mcp__google-workspace__gmail_create_draft"

read -r -d '' PROMPT <<PROMPT_EOF
You are Jimmy running as an unattended scheduled queue sweep on athena. There is
no human watching this run.

Load and follow ${POPS_DIR}/skills/domain/jimmy.md (Queue Workflow) and
${POPS_DIR}/skills/domain/trac.md (MoinMoin syntax, ASCII only, no backticks).

Scope for THIS run is TRIAGE ONLY:

1. Fetch the queue with trac_search_tickets("owner=jimmy&status=!closed").
2. Handle at most ${MAX_TICKETS} tickets, least-recently-changed first.
3. For each, read it with trac_get_ticket and classify it into a lane per
   jimmy.md:
   - Decision needed: post ONE concise comment stating the specific question,
     with single-keystroke options ([1], [2]) and a recommendation, then set
     owner=will.
   - Email needed: post the draft email as ONE comment, then set owner=will.
     Do NOT create or send anything in Gmail.
   - Autonomous: post ONE short comment recording the concrete next step you
     would take. Do NOT perform the work in this run.
4. Hard limits: never close a ticket, never change priority, component, type or
   keywords, and never send or draft email outside a Trac comment.
5. If a ticket already has a recent sweep comment and nothing has changed since,
   skip it silently rather than repeating yourself.
6. Sign every comment: jimmy (claude@athena, scheduled sweep).
7. Finish with one line per ticket touched, then stop.
PROMPT_EOF

if [ "${1:-}" = "--dry-run" ]; then
    echo "POPS_DIR=$POPS_DIR"
    echo "ALLOWED=$ALLOWED"
    echo "DISALLOWED=$DISALLOWED"
    echo "TIMEOUT=${RUN_TIMEOUT}s  MAX_TICKETS=$MAX_TICKETS"
    echo "--- prompt ---"; echo "$PROMPT"
    exit 0
fi

cd "$POPS_DIR" || { log "FATAL: cannot cd to $POPS_DIR"; exit 1; }

log "START sweep (max=$MAX_TICKETS timeout=${RUN_TIMEOUT}s)"

# ANTHROPIC_API_KEY in ~/.bashrc is stale and takes precedence over the working
# claude.ai credentials, yielding "401 API key is invalid" in headless runs.
# Unset it for this invocation only. See Trac #4456.
# Open the lock on fd 9 in THIS shell before taking it. Do not fold this into a
# command substitution: fd 9 is not open inside that subshell, flock then fails,
# and every run silently reports "another sweep is running" while never running.
exec 9>"$LOCK"
if ! flock -n 9; then
    log "SKIP: another sweep is already running"
    exit 0
fi

out=$(timeout "$RUN_TIMEOUT" env -u ANTHROPIC_API_KEY \
        claude -p "$PROMPT" \
          --allowedTools $ALLOWED \
          --disallowedTools $DISALLOWED 2>&1)
rc=$?

printf '%s\n' "$out" | sed 's/^/    /' >> "$LOG"
if [ $rc -eq 124 ]; then
    log "END rc=$rc (TIMED OUT after ${RUN_TIMEOUT}s)"
else
    log "END rc=$rc"
fi
exit $rc
