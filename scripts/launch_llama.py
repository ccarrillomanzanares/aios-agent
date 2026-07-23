#!/usr/bin/env python3
"""Launch llama-server with parameters from ~/.aios/config.yaml."""
import os
import subprocess
import sys
import time
from pathlib import Path

CONFIG_FILE = Path.home() / ".aios" / "config.yaml"
LLAMA_BIN = Path.home() / "llama.cpp" / "build" / "bin" / "llama-server"
MODELS_DIR = Path.home() / "models"


def main():
    # Wait for config to exist (firstboot may still be running)
    for _ in range(30):
        if CONFIG_FILE.exists():
            break
        time.sleep(2)
    else:
        print("[aios-llama] No config.yaml found after 60s. Exiting.", flush=True)
        sys.exit(1)

    import yaml
    with open(CONFIG_FILE) as f:
        config = yaml.safe_load(f)

    local = config.get("local", {})
    model_file = local.get("model", "Qwen_Qwen3-8B-Q4_K_M.gguf")
    context = local.get("context", 32768)
    threads = local.get("threads", os.cpu_count() or 4)

    model_path = MODELS_DIR / model_file
    if not model_path.exists():
        print(f"[aios-llama] Model not found: {model_path}", flush=True)
        sys.exit(1)

    cmd = [
        str(LLAMA_BIN),
        "-m", str(model_path),
        "--host", "127.0.0.1",
        "--port", "8083",
        "-c", str(context),
        "-t", str(threads),
        "--jinja",
    ]

    print(f"[aios-llama] Starting: {' '.join(cmd)}", flush=True)
    os.execvp(str(LLAMA_BIN), cmd)


if __name__ == "__main__":
    main()
