#!/bin/bash
# WP-2 acceptance harness for Trac #4494. Exercises the state machine against
# stubbed df/mail/logger. No real filesystem and no real MTA are involved.
set -u
D="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$D/check_disk.sh"
export DISK_ALERT_DF_CMD="$D/stub_df"
export DISK_ALERT_MAIL_CMD="$D/stub_mail"
export DISK_ALERT_LOGGER_CMD="$D/stub_logger"
export DISK_ALERT_STATE_DIR="$D/state"
export MAILLOG="$D/maillog"
T0=1788000000
pass=0; fail=0
reset(){ rm -rf "$D/state" "$MAILLOG"; mkdir -p "$D/state"; : > "$MAILLOG"; }
run(){ FIX_BLOCK="$1" FIX_INODE="$2" DISK_ALERT_NOW="$3" FAIL_MAIL="${4:-0}" \
       bash "$SCRIPT" >"$D/out" 2>"$D/err"; echo $?; }
sent(){ grep -c "^MAILSENT" "$MAILLOG" 2>/dev/null || true; }
check(){ if [ "$2" = "$3" ]; then echo "  PASS  $1 ($2)"; pass=$((pass+1));
         else echo "  FAIL  $1: expected '$3' got '$2'"; fail=$((fail+1)); fi }

echo "T1 sustained breach alerts once, then stays quiet inside the window"
reset
run " 92% /" " 11% /" $T0            >/dev/null; check "first breach alerts"      "$(sent)" 1
run " 92% /" " 11% /" $((T0+3600))   >/dev/null; check "+1h no repeat"            "$(sent)" 1
run " 92% /" " 11% /" $((T0+82800))  >/dev/null; check "+23h no repeat"           "$(sent)" 1

echo "T2 re-notifies once the 24h interval elapses (the once-forever fix)"
run " 92% /" " 11% /" $((T0+86400))  >/dev/null; check "+24h re-alerts"           "$(sent)" 2
grep -q 'still breached' "$MAILLOG"; check "repeat subject tagged"  "$?" "0"
run " 92% /" " 11% /" $((T0+90000))  >/dev/null; check "+25h quiet again"         "$(sent)" 2

echo "T3 hysteresis: 82% is below alert but above clear, state is retained"
run " 82% /" " 11% /" $((T0+180000)) >/dev/null; check "no alert at 82%"          "$(sent)" 2
check "state retained in band" "$(ls "$D/state" | wc -l)" 1

echo "T4 dropping below the clear threshold clears state"
run " 70% /" " 11% /" $((T0+190000)) >/dev/null; check "no alert at 70%"          "$(sent)" 2
check "state cleared"          "$(ls "$D/state" | wc -l)" 0
run " 92% /" " 11% /" $((T0+200000)) >/dev/null; check "re-breach alerts fresh"   "$(sent)" 3

echo "T5 failed delivery is NOT latched as sent"
reset
rc=$(run " 92% /" " 11% /" $T0 1);              check "exit non-zero on failure"  "$rc" 1
check "no mail recorded"       "$(sent)" 0
check "no state written"       "$(ls "$D/state" | wc -l)" 0
grep -q 'ALERT DELIVERY FAILED' "$D/err"; check "failure on stderr" "$?" "0"
run " 92% /" " 11% /" $((T0+60))     >/dev/null; check "next run retries"         "$(sent)" 1

echo "T6 inode exhaustion alerts while blocks read normal"
reset
run " 40% /" " 95% /" $T0            >/dev/null; check "inode breach alerts"      "$(sent)" 1
grep -q 'inodes' "$MAILLOG"; check "subject names inodes" "$?" "0"

echo "T7 excluded mounts are skipped"
reset
run " 99% /boot/efi
 40% /" " 11% /
 11% /" $T0 >/dev/null;                          check "excluded mount ignored"   "$(sent)" 0

echo "T8 heartbeat emitted on a clean run"
reset
run " 40% /" " 11% /" $T0            >/dev/null
grep -q 'heartbeat' "$MAILLOG"; check "heartbeat logged" "$?" "0"

echo "T9 multiple filesystems tracked independently"
reset
run " 92% /
 91% /var" " 11% /
 11% /var" $T0 >/dev/null;                       check "two breaches, two mails"  "$(sent)" 2
check "two state files"        "$(ls "$D/state" | wc -l)" 2

echo
echo "RESULT: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
