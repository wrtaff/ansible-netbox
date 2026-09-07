#!/usr/bin/env bash
killall -9 polybar 2>/dev/null
while pgrep -u $UID -x polybar >/dev/null; do sleep 1; done

PRIMARY_MON=$(xrandr --query 2>/dev/null | grep " connected" | grep "primary" | cut -d" " -f1)

if [ -z "$PRIMARY_MON" ]; then
  polybar --reload primary 2>&1 | tee -a /tmp/polybar.log & disown
else
  for m in $(xrandr --query | grep " connected" | cut -d" " -f1); do
    if [ "$m" = "$PRIMARY_MON" ]; then
      MONITOR=$m polybar --reload primary 2>&1 | tee -a /tmp/polybar-$m.log & disown
    else
      MONITOR=$m polybar --reload main 2>&1 | tee -a /tmp/polybar-$m.log & disown
    fi
  done
fi
