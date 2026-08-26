#!/bin/bash
# Graba pantalla completa indefinidamente, desligado de la terminal.
# Parada: kill -INT $(cat /tmp/grabar.pid)  o  scripts/parar_grabacion.sh
OUT=/tmp/grabacion.mp4
LOG=/tmp/grabar.log
rm -f "$OUT" "$LOG"
setsid nohup ffmpeg -y -nostdin -loglevel error \
  -f x11grab -framerate 25 -video_size 1366x768 -i :0.0 \
  -c:v libx264 -preset veryfast -crf 23 -pix_fmt yuv420p "$OUT" \
  > "$LOG" 2>&1 &
echo $! > /tmp/grabar.pid
echo "Grabando. PID=$(cat /tmp/grabar.pid). Para parar: kill -INT \$(cat /tmp/grabar.pid)"
