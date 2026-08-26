#!/bin/bash
# Parada limpia: SIGINT a ffmpeg -> sella el moov correctamente.
PID=$(cat /tmp/grabar.pid 2>/dev/null)
if [ -z "$PID" ] || ! kill -0 "$PID" 2>/dev/null; then
  echo "No hay grabación activa."
  exit 1
fi
echo "Enviando SIGINT a ffmpeg (PID $PID)..."
kill -INT "$PID"
# Esperar a que termine de escribir el índice
for i in $(seq 1 50); do
  kill -0 "$PID" 2>/dev/null || break
  sleep 0.2
done
if kill -0 "$PID" 2>/dev/null; then
  echo "ffmpeg sigue vivo; forzando SIGTERM"
  kill -TERM "$PID"
fi
sleep 1
echo "Detenido. Resultado:"
ls -la /tmp/grabacion.mp4
