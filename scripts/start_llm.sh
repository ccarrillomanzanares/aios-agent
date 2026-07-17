#!/bin/bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Modelo por defecto. Puedes cambiarlo temporalmente con:
#   MODEL=models/otro.gguf ./scripts/start_llm.sh
MODEL="${MODEL:-${BASE_DIR}/models/Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf}"
THREADS="${THREADS:-$(nproc)}"
CTX=8192

if [ ! -f "$MODEL" ]; then
    echo "Modelo no encontrado: $MODEL"
    exit 1
fi

echo "Arrancando llama-server con: $MODEL"

export LD_LIBRARY_PATH="${BASE_DIR}/llama.cpp/build/bin:${LD_LIBRARY_PATH:-}"

exec "${BASE_DIR}/llama.cpp/build/bin/llama-server" \
  -m "$MODEL" \
  -c "$CTX" \
  -t "$THREADS" \
  --host 127.0.0.1 \
  --port 8080
