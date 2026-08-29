#!/bin/bash
# Install screen recording: copy scripts to ~/.local/bin and add the $mod+Print
# shortcut to the i3 config (idempotent).
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
    echo "✓ Shortcut already in i3 config."
  else
    # Insert before the first bindsym F1 if it exists, otherwise append
    if grep -q '^bindsym F1 ' "$I3_CONFIG"; then
      sed -i "/^bindsym F1 /i $ATALLO" "$I3_CONFIG"
    else
      echo "$ATALLO" >> "$I3_CONFIG"
    fi
    echo "✓ Shortcut added: $ATALLO"
  fi
  DISPLAY="${DISPLAY:-:0}" i3-msg reload > /dev/null 2>&1 && echo "✓ i3 reloaded."
else
  echo "⚠ Could not find $I3_CONFIG — add manually: $ATALLO"
fi
echo "✔ Screen recording installed. Use Mod+Print to start/stop."
