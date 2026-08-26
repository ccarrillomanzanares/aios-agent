#!/bin/bash
# Toggle de grabación de pantalla para i3 (enlazado a $mod+Print).
# Inicia si no hay grabación; la detiene limpiamente si la hay.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE=/tmp/grabar.pid

notify() {
  if command -v notify-send >/dev/null 2>&1; then
    notify-send -t 2500 "Grabación de pantalla" "$1"
  fi
}

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  "$DIR/parar_grabacion.sh" > /dev/null 2>&1
  notify "⏹ Detenida → /tmp/grabacion.mp4"
  echo "⏹ Grabación detenida: $(ls -la /tmp/grabacion.mp4 2>/dev/null | awk '{print $5}') bytes"
else
  "$DIR/grabar.sh" > /dev/null 2>&1
  notify "⏺ Grabando... ($(cat "$PID_FILE"))"
  echo "⏺ Grabando PID=$(cat "$PID_FILE")"
fi
