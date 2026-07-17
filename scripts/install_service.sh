#!/bin/bash
set -euo pipefail
BASE=/home/ccmai/sre-copilot
cd "$BASE"
source venv/bin/activate
mkdir -p "$HOME/.config/systemd/user"
cp "$BASE/systemd/sre-llm.service" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable sre-llm.service
systemctl --user start sre-llm.service
systemctl --user status sre-llm.service --no-pager
