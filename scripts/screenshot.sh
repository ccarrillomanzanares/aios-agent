#!/bin/sh
# Pantallazo a ~/screenshots/.
# Vive en su propio script (no inline en i3) para evitar el % del strftime
# y las comillas anidadas, que rompían el parser de i3.
mkdir -p "$HOME/screenshots"
exec scrot "$HOME/screenshots/shot-$(date +%Y-%m-%d_%H%M%S).png"
