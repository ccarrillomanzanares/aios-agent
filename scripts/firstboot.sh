#!/usr/bin/bash -e
# AIOS Agent - First boot setup
# Runs once on first boot to initialize the configuration.

CONFIG_FILE="$HOME/.aios/config.yaml"
MODELS_DIR="$HOME/models"
AGENT_DIR="/usr/local/bin/aios-agent"

echo "============================================"
echo "  AIOS Agent - First Boot Setup"
echo "============================================"
echo ""

# Check if already configured
if [ -f "$CONFIG_FILE" ]; then
    echo "  Config found at $CONFIG_FILE"
    echo "  Skipping setup. Remove it to reconfigure."
    echo ""
    echo "  Start the agent:  python3 $AGENT_DIR/chat.py"
    echo ""
    exit 0
fi

# Run the setup wizard
cd "$AGENT_DIR"
python3 setup.py

# If model was already downloaded, start the server
MODEL=$(grep 'model:' "$CONFIG_FILE" | head -1 | awk '{print $2}' | tr -d '"')
if [ -n "$MODEL" ] && [ -f "$MODELS_DIR/$MODEL" ]; then
    echo ""
    echo "  Model found. Enabling and starting services..."
    systemctl --user enable aios-llama.service
    systemctl --user enable aios-agent.service
    systemctl --user start aios-llama.service
fi

echo ""
echo "  Setup complete!"
echo "  Reboot or run:  python3 $AGENT_DIR/chat.py"
echo ""
