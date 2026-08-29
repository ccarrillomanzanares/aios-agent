#!/bin/bash
# Clean stop: SIGINT to ffmpeg → seals the moov correctly.
PID=$(cat /tmp/grabar.pid 2>/dev/null)
if [ -z "$PID" ] || ! kill -0 "$PID" 2>/dev/null; then
  echo "No active recording."
  exit 1
fi
echo "Sending SIGINT to ffmpeg (PID $PID)..."
kill -INT "$PID"
# Wait for it to finish writing the index
for i in $(seq 1 50); do
  kill -0 "$PID" 2>/dev/null || break
  sleep 0.2
done
if kill -0 "$PID" 2>/dev/null; then
  echo "ffmpeg is still alive; forcing SIGTERM"
  kill -TERM "$PID"
fi
sleep 1
echo "Stopped. Result:"
ls -la /tmp/grabacion.mp4
