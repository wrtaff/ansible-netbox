#!/usr/bin/env bash
# =============================================================================
# Filename:       smoke.sh
# Version:        1.0
# Author:         Claude Code
# Last Modified:  2026-06-10
# Context:        http://trac.home.arpa/ticket/3577
#
# Purpose:
#     Manual smoke test against a RUNNING Pops KMS REST API server. Curls
#     /api/health, exercises /api/inbox auth (401/403) and a real capture
#     (201), and checks /api/search success (200) and the blank-query error
#     (400). Prints PASS/FAIL per check and exits non-zero if any check fails.
#
#     WARNING: the inbox 201 check performs a real capture and therefore
#     WRITES to the live POPS_ROOT of the server under test (a journal file
#     under raw/journal/ and a line in wiki/log.md). Do not run against a
#     server whose pops tree you care about unless you accept that write.
#
# Secrets:
#     POPS_API_KEY  (env var) - API key for the server under test. Never
#                   echoed by this script.
#
# Usage:
#     POPS_API_KEY=devkey ./tests/smoke.sh
#     POPS_API_URL=http://athena:8765 POPS_API_KEY=devkey ./tests/smoke.sh
#
# Revision History:
#     1.0 - Initial test suite (Phase 1 subtask P1.7). Trac #3577.
# =============================================================================

set -u

POPS_API_URL="${POPS_API_URL:-http://127.0.0.1:8765}"

if [ -z "${POPS_API_KEY:-}" ]; then
    echo "FATAL: POPS_API_KEY environment variable is required." >&2
    exit 2
fi

FAILS=0

# check NAME EXPECTED_STATUS  curl-args...
# Issues the curl, captures the HTTP status, and reports PASS/FAIL.
check() {
    local name="$1"
    local expected="$2"
    shift 2
    local actual
    actual="$(curl -s -o /dev/null -w '%{http_code}' "$@")"
    if [ "$actual" = "$expected" ]; then
        echo "PASS  ${name} (HTTP ${actual})"
    else
        echo "FAIL  ${name} (expected HTTP ${expected}, got ${actual})"
        FAILS=$((FAILS + 1))
    fi
}

echo "Smoke testing ${POPS_API_URL}"
echo "WARNING: the inbox 201 check writes to the live POPS_ROOT of that server."
echo

# --- health (no auth) ---
check "health 200" 200 \
    "${POPS_API_URL}/api/health"

# --- inbox auth failures ---
check "inbox missing key 401" 401 \
    -X POST -H 'Content-Type: application/json' \
    -d '{"text":"smoke"}' \
    "${POPS_API_URL}/api/inbox"

check "inbox wrong key 403" 403 \
    -X POST -H 'Content-Type: application/json' \
    -H 'X-API-Key: wrong-key' \
    -d '{"text":"smoke"}' \
    "${POPS_API_URL}/api/inbox"

# --- inbox real capture (WRITES to live pops tree) ---
check "inbox capture 201" 201 \
    -X POST -H 'Content-Type: application/json' \
    -H "X-API-Key: ${POPS_API_KEY}" \
    -d '{"text":"smoke.sh capture probe","source":"smoke"}' \
    "${POPS_API_URL}/api/inbox"

# --- search ---
check "search 200" 200 \
    -H "X-API-Key: ${POPS_API_KEY}" \
    -G --data-urlencode 'q=the' \
    "${POPS_API_URL}/api/search"

check "search blank q 400" 400 \
    -H "X-API-Key: ${POPS_API_KEY}" \
    -G --data-urlencode 'q=' \
    "${POPS_API_URL}/api/search"

echo
if [ "$FAILS" -eq 0 ]; then
    echo "ALL CHECKS PASSED"
    exit 0
else
    echo "${FAILS} CHECK(S) FAILED"
    exit 1
fi
