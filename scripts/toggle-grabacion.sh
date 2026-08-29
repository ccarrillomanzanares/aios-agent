#!/bin/bash
# Screen recording toggle for i3 (bound to $mod+Print).
# Starts if no recording is active; stops cleanly if one is.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE=/tmp/grabar.pid

notify() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send -t 2500 "Screen recording" "$1"
  fi
}

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  "$DIR/parar_grabacion.sh" > /dev/null 2>&1
  notify "⏹ Stopped → /tmp/grabacion.mp4"
  echo "⏹ Recording stopped: $(ls -la /tmp/grabacion.mp4 2>/dev/null | awk '{print $5}') bytes"
else
  "$DIR/grabar.sh" > /dev/null 2>&1
  notify "⏺ Recording... ($(cat "$PID_FILE"))"
  echo "⏺ Recording PID=$(cat "$PID_FILE")"
fi
