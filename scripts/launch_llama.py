#!/usr/bin/env python3
"""Launch llama-server if config exists and mode is local."""
import os, sys, time
from pathlib import Path
os.environ["LD_LIBRARY_PATH"] = "/usr/local/lib/llama:" + os.environ.get("LD_LIBRARY_PATH", "")
CONFIG_FILE = Path.home() / ".aios" / "config.yaml"
LLAMA_BIN = "/usr/local/bin/llama-server"
MODELS_DIR = Path("/usr/local/share/aios/models")

def main():
    # No crear config. Si no existe, salir (el wizard de chat.py lo creara)
    if not CONFIG_FILE.exists():
        print("[aios-llama] No config yet. Setup will run on first login.", flush=True)
        sys.exit(0)
    import yaml
    with open(CONFIG_FILE) as f: cfg = yaml.safe_load(f)
    if cfg.get("mode") != "local":
        print("[aios-llama] Cloud mode - not starting local model", flush=True)
        sys.exit(0)
    mn = cfg.get("local", {}).get("model", "Qwen_Qwen3-8B-Q4_K_M.gguf")
    mp = MODELS_DIR / mn
    if not mp.exists():
        print(f"[aios-llama] Model not found: {mp}", flush=True)
        sys.exit(1)
    ctx = cfg.get("local", {}).get("context", 32768)
    thr = cfg.get("local", {}).get("threads", 14)
    cmd = [LLAMA_BIN, "-m", str(mp), "--host","127.0.0.1","--port","8083","-c",str(ctx),"-t",str(thr),"--jinja"]
    print(f"[aios-llama] Starting {mp.name} ({mp.stat().st_size//(1024**3)}GB, {ctx}ctx)", flush=True)
    os.execvp(LLAMA_BIN, cmd)

if __name__ == "__main__":
    main()
