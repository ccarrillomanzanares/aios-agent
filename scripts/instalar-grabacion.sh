#!/bin/bash
# Instala la grabación de pantalla: copia scripts a ~/.local/bin y
# añade el atajo $mod+Print al config de i3 (idempotente).
set -e
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
I3_CONFIG="$HOME/.config/i3/config"
ATALLO='bindsym $mod+Print exec ~/.local/bin/toggle-grabacion.sh'

mkdir -p "$BIN_DIR"
install -m 755 "$SRC/grabar.sh"        "$BIN_DIR/grabar.sh"
install -m 755 "$SRC/parar_grabacion.sh" "$BIN_DIR/parar_grabacion.sh"
install -m 755 "$SRC/toggle-grabacion.sh" "$BIN_DIR/toggle-grabacion.sh"

if [ -f "$I3_CONFIG" ]; then
  if grep -q "toggle-grabacion" "$I3_CONFIG"; then
    echo "✓ El atajo ya está en el config de i3."
  else
    # Insertar antes del primer bindsym F1 si existe, si no al final
    if grep -q '^bindsym F1 ' "$I3_CONFIG"; then
      sed -i "/^bindsym F1 /i $ATALLO" "$I3_CONFIG"
    else
      echo "$ATALLO" >> "$I3_CONFIG"
    fi
    echo "✓ Atajo añadido: $ATALLO"
  fi
  DISPLAY="${DISPLAY:-:0}" i3-msg reload > /dev/null 2>&1 && echo "✓ i3 recargado."
else
  echo "⚠ No se encontró $I3_CONFIG — añade manualmente: $ATALLO"
fi
echo "✔ Grabación de pantalla instalada. Usa Mod+Print para iniciar/parar."
