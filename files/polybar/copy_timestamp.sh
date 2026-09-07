#!/usr/bin/env bash
export DISPLAY=${DISPLAY:-:0}
TS=$(date --iso-8601=seconds)
echo -n "$TS" | xclip -selection primary
echo -n "$TS" | xclip -selection clipboard
echo -n "$TS" | xsel --primary --input 2>/dev/null || true
echo -n "$TS" | xsel --clipboard --input 2>/dev/null || true
notify-send -u normal -t 2000 "Timestamp Copied" "$TS" 2>/dev/null || true
