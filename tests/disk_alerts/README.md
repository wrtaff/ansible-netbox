# disk_alerts acceptance harness (Trac #4494 WP-2)

Exercises the `check_disk.sh` state machine against stubbed `df`, `mail` and
`logger`. No real filesystem, no real MTA, no host state is touched.

## Why this exists

The pre-WP-2 script latched on a lock file with no expiry, so a filesystem that
stayed above threshold alerted exactly once and then went silent forever
(pve5 sat at 92% for 20 days). The regressions worth guarding are all timing-
or delivery-dependent and cannot be caught by `bash -n`.

## Running

Render the template first, then run the harness against the rendered script:

```
python3 -c "
import yaml, jinja2
d = yaml.safe_load(open('roles/disk_alerts/defaults/main.yml'))
env = jinja2.Environment(keep_trailing_newline=True)
print(env.from_string(open('roles/disk_alerts/templates/check_disk.sh.j2').read()).render(**d), end='')
" > tests/disk_alerts/check_disk.sh
bash tests/disk_alerts/run_tests.sh
```

Requires `python3-yaml` and `python3-jinja2` (present on athena, absent on the
agent runners).

## Test seams

The script reads these environment variables so the harness can drive it.
They are unset in production and the script falls back to real binaries.

| Variable | Purpose |
|---|---|
| `DISK_ALERT_DF_CMD` | stub `df` |
| `DISK_ALERT_MAIL_CMD` | stub `mail` |
| `DISK_ALERT_LOGGER_CMD` | stub `logger` |
| `DISK_ALERT_STATE_DIR` | redirect state away from `/var/lib/disk_alert` |
| `DISK_ALERT_NOW` | pin "now" so re-notify intervals can be simulated |

## Coverage

| Test | Guards against |
|---|---|
| T1 | re-alerting inside the re-notify window |
| T2 | **the once-forever defect** -- sustained breach must re-alert at the interval |
| T3 | boundary flapping -- state must survive the hysteresis band |
| T4 | state must clear below the clear threshold, and re-arm |
| T5 | **a failed delivery must not be recorded as sent**, and must retry |
| T6 | inode exhaustion while block usage reads normal |
| T7 | excluded mounts |
| T8 | heartbeat on a clean run (distinguishes "no alerts" from "no monitor") |
| T9 | independent state per filesystem |
