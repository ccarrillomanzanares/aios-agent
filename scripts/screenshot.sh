#!/bin/sh
# Screenshot to ~/screenshots/.
# Lives in its own script (not inline in i3) to avoid the % from strftime
# and nested quotes, which broke the i3 parser.
mkdir -p "$HOME/screenshots"
exec scrot "$HOME/screenshots/shot-$(date +%Y-%m-%d_%H%M%S).png"
