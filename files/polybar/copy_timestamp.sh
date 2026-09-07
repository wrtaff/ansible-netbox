#!/usr/bin/env bash
TS=$(date --iso-8601=seconds)
printf "%s" "$TS" | xclip -selection primary -in
printf "%s" "$TS" | xclip -selection clipboard -in
notify-send "Copied Timestamp" "$TS" -t 2000 2>/dev/null || true
