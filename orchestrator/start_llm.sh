#!/bin/bash
set -euo pipefail

BASE=/home/ccmai/sre-copilot
MODEL="${BASE}/models/Qwen_Qwen3-8B-Q5_K_M.gguf"
THREADS=16
CTX=8192

if [ ! -f "$MODEL" ]; then
    echo "Modelo no encontrado: $MODEL"
    exit 1
fi

export LD_LIBRARY_PATH="${BASE}/llama.cpp/build/bin:${LD_LIBRARY_PATH:-}"

exec "${BASE}/llama.cpp/build/bin/llama-server" \
  -m "$MODEL" \
  -c "$CTX" \
  -t "$THREADS" \
  --host 127.0.0.1 \
  --port 8080
