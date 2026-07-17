#!/bin/bash
# setup.sh — Instalador automático de aios-agent en una máquina Linux.
# Requisitos mínimos: CPU x86_64 con AVX2, ~8 GB de RAM libres, ~10 GB de disco.
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODEL_NAME="${MODEL_NAME:-Meta-Llama-3.1-8B-Instruct-Q5_K_M.gguf}"
MODEL_REPO="${MODEL_REPO:-bartowski/Meta-Llama-3.1-8B-Instruct-GGUF}"
LLAMA_TAG="${LLAMA_TAG:-b5200}"
THREADS="${THREADS:-$(nproc)}"

PYTHON="${PYTHON:-python3}"
VENV_DIR="$BASE_DIR/venv"
MODELS_DIR="$BASE_DIR/models"
LOGS_DIR="$BASE_DIR/logs"
LLAMA_DIR="$BASE_DIR/llama.cpp"

color() { printf '\033[%sm%s\033[0m\n' "$1" "$2"; }
info() { color '1;34' "[INFO] $1"; }
ok() { color '1;32' "[OK] $1"; }
warn() { color '1;33' "[WARN] $1"; }
err() { color '1;31' "[ERROR] $1"; exit 1; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

check_system() {
    info "Verificando sistema..."
    [ "$(uname -m)" = "x86_64" ] || warn "Arquitectura no x86_64 detectada. llama.cpp puede no funcionar óptimamente."
    grep -q 'avx2' /proc/cpuinfo || warn "CPU sin AVX2 detectada. El rendimiento del LLM será muy bajo."
    ok "Sistema compatible."
}

check_deps() {
    info "Verificando dependencias del sistema..."
    local missing=""
    for cmd in git curl wget "$PYTHON" pip3 make cmake g++ gcc; do
        command_exists "$cmd" || missing="$missing $cmd"
    done
    if [ -n "$missing" ]; then
        err "Faltan dependencias:$missing. Instálalas con tu gestor de paquetes (apt/dnf/pacman) y vuelve a ejecutar setup.sh."
    fi
    ok "Dependencias del sistema OK."
}

setup_venv() {
    info "Configurando entorno Python..."
    if [ ! -d "$VENV_DIR" ]; then
        "$PYTHON" -m venv "$VENV_DIR"
    fi
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip setuptools wheel
    pip install -r "$BASE_DIR/requirements.txt"
    ok "Entorno Python listo."
}

build_llama() {
    info "Compilando llama.cpp (tag $LLAMA_TAG)..."
    if [ ! -d "$LLAMA_DIR" ]; then
        git clone --depth 1 --branch "$LLAMA_TAG" https://github.com/ggerganov/llama.cpp.git "$LLAMA_DIR"
    fi
    cd "$LLAMA_DIR"
    cmake -B build -DLLAMA_CUDA=OFF -DLLAMA_VULKAN=OFF -DLLAMA_OPENMP=ON
    cmake --build build --config Release -j "$THREADS"
    ok "llama.cpp compilado en $LLAMA_DIR/build/bin/llama-server"
}

download_model() {
    info "Descargando modelo $MODEL_NAME..."
    mkdir -p "$MODELS_DIR"
    local model_path="$MODELS_DIR/$MODEL_NAME"
    if [ -f "$model_path" ]; then
        ok "Modelo ya existe: $model_path"
        return
    fi

    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"

    if command_exists hf; then
        hf download "$MODEL_REPO" --include "$MODEL_NAME" --local-dir "$MODELS_DIR"
    else
        warn "CLI 'hf' no disponible. Intentando descarga con huggingface-hub..."
        pip install -q huggingface-hub
        "$PYTHON" - <<PY
from huggingface_hub import hf_hub_download
hf_hub_download(repo_id="$MODEL_REPO", filename="$MODEL_NAME", local_dir="$MODELS_DIR", local_dir_use_symlinks=False)
PY
    fi

    [ -f "$model_path" ] || err "No se pudo descargar el modelo $MODEL_NAME"
    ok "Modelo descargado: $model_path"
}

rebuild_index() {
    info "Reconstruyendo índice RAG..."
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    mkdir -p "$BASE_DIR/rag/chroma_db"
    "$PYTHON" "$BASE_DIR/rag/build_index.py" --input "$BASE_DIR/data/external" --db "$BASE_DIR/rag/chroma_db" --reset
    ok "Índice RAG reconstruido."
}

create_dirs() {
    mkdir -p "$LOGS_DIR" "$BASE_DIR/rag/chroma_db" "$MODELS_DIR"
}

print_next_steps() {
    cat <> "EOF"

$(color '1;32' "Instalación completada.")

Pasos siguientes:

1. Arrancar el servidor LLM:
   $(color '0;36' "cd $BASE_DIR && source venv/bin/activate && scripts/start_llm.sh")

2. En otra terminal, lanzar el orquestador:
   $(color '0;36' "cd $BASE_DIR && source venv/bin/activate && python orchestrator/main.py")

3. Ejecutar tests:
   $(color '0;36' "cd $BASE_DIR && source venv/bin/activate && python scripts/evaluate.py")

Para ejecutar llama-server como servicio systemd del usuario, copia y adapta
scripts/install_service.sh (si existe) o crea tu propia unit.
EOF
}

main() {
    check_system
    check_deps
    create_dirs
    setup_venv
    build_llama
    download_model
    rebuild_index
    print_next_steps
}

main "$@"
