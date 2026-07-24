#!/usr/bin/env python3
"""Launch llama-server. Creates default config if none exists (live ISO)."""
import os, sys, time
from pathlib import Path
os.environ["LD_LIBRARY_PATH"] = "/usr/local/lib/llama:" + os.environ.get("LD_LIBRARY_PATH", "")
CONFIG_FILE = Path.home() / ".aios" / "config.yaml"
LLAMA_BIN = "/usr/local/bin/llama-server"
MODELS_DIR = Path("/usr/local/share/aios/models")
FALLBACK_DIRS = [Path.home() / "models"]

def _cpu():
    return max(1, int((os.cpu_count() or 4) * 0.875))
def _ram():
    try:
        with open("/proc/meminfo") as f:
            for l in f:
                if l.startswith("MemTotal:"): return round(int(l.split()[1])/1024/1024)
    except: return 12
def _ctx(r):
    return 8192 if r<=8 else 32768 if r<=16 else 65536
def _model():
    if MODELS_DIR.exists():
        for f in MODELS_DIR.glob("*.gguf"): return f
    for d in FALLBACK_DIRS:
        if d.exists():
            for f in d.glob("*.gguf"): return f
    return MODELS_DIR / "Qwen_Qwen3-8B-Q4_K_M.gguf"
def _gen_config():
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    import yaml
    mp = _model()
    with open(CONFIG_FILE, "w") as f:
        yaml.dump({"mode":"local","local":{"model":mp.name,"model_name":"Qwen3-8B-Instruct","threads":_cpu(),"context":_ctx(_ram())},"cloud":{"provider":None,"model":None}}, f)
    print(f"[aios-llama] Config created ({_ctx(_ram())//1024}K ctx)", flush=True)

def main():
    if not CONFIG_FILE.exists():
        _gen_config()
    import yaml
    with open(CONFIG_FILE) as f: cfg = yaml.safe_load(f)
    if cfg.get("mode") != "local":
        print("[aios-llama] Cloud mode - not starting local model", flush=True)
        sys.exit(0)  # Exit cleanly, no restart
    local = cfg.get("local", {})
    mn = local.get("model", "Qwen_Qwen3-8B-Q4_K_M.gguf")
    mp = MODELS_DIR / mn
    if not mp.exists():
        for d in FALLBACK_DIRS:
            p = d / mn
            if p.exists(): mp = p; break
    if not mp.exists():
        print(f"[aios-llama] Model not found: {mp}", flush=True)
        sys.exit(1)
    ctx = local.get("context", _ctx(_ram()))
    thr = local.get("threads", _cpu())
    cmd = [LLAMA_BIN, "-m", str(mp), "--host","127.0.0.1","--port","8083","-c",str(ctx),"-t",str(thr),"--jinja"]
    print(f"[aios-llama] Starting {mp.name} ({mp.stat().st_size//(1024**3)}GB, {ctx}ctx)", flush=True)
    os.execvp(LLAMA_BIN, cmd)

if __name__ == "__main__":
    main()
