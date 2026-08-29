#!/bin/bash
# Record full screen indefinitely, detached from the terminal.
# Stop: kill -INT $(cat /tmp/grabar.pid)  or  scripts/parar_grabacion.sh
OUT=/tmp/grabacion.mp4
LOG=/tmp/grabar.log
rm -f "$OUT" "$LOG"
setsid nohup ffmpeg -y -nostdin -loglevel error \
  -f x11grab -framerate 25 -video_size 1366x768 -i :0.0 \
  -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "$OUT" \
  > "$LOG" 2>&1 &
echo $! > /tmp/grabar.pid
echo "Recording. PID=$(cat /tmp/grabar.pid). To stop: kill -INT \$(cat /tmp/grabar.pid)"
