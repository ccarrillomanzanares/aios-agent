import readline
readline.parse_and_bind('"\\d": backward-delete-char')
"""AIOS Agent - Configuration setup (first-run wizard)."""
import json
import os
import urllib.request as url_req

CLOUD_ENDPOINTS = {
    "DeepSeek": "https://api.deepseek.com/v1",
    "OpenAI": "https://api.openai.com/v1",
    "Anthropic": "https://api.anthropic.com/v1",
    "Google Gemini": "https://generativelanguage.googleapis.com/v1beta",
    "Kimi / Moonshot": "https://api.moonshot.cn/v1",
    "Ollama Cloud": "https://api.ollama.cloud/v1",
    "OpenRouter": "https://openrouter.ai/api/v1",
}

def validate_api_key(provider, api_key):
    """Test the API key with a lightweight request (hard timeout, DNS-safe)."""
    import threading

    base_url = CLOUD_ENDPOINTS.get(provider, "")
    if not base_url:
        return True  # Unknown provider, skip validation

    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "AIOS-Setup/1.0"
    }
    result = {}

    def _check():
        try:
            if provider == "Google Gemini":
                req = url_req.Request(f"{base_url}/models?key={api_key}", method="GET")
            elif provider == "Anthropic":
                req = url_req.Request(f"{base_url}/messages", method="POST",
                                    data=b'{"model":"claude-3-haiku-20240307","max_tokens":1,"messages":[{"role":"user","content":"hi"}]}',
                                    headers={**headers, "Content-Type": "application/json", "anthropic-version": "2023-06-01"})
            else:
                req = url_req.Request(f"{base_url}/models", headers=headers, method="GET")

            with url_req.urlopen(req, timeout=5) as resp:
                result["value"] = resp.status < 400
        except url_req.HTTPError as e:
            result["value"] = False if e.code in (401, 403) else None
        except Exception:
            result["value"] = None

    t = threading.Thread(target=_check, daemon=True)
    t.start()
    t.join(timeout=12)  # hard cap: incluye resolución DNS y conexión
    return result.get("value")
import platform
from pathlib import Path

CONFIG_DIR = Path.home() / ".aios"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def detect_cpu():
    """Return recommended thread count (87.5% of cores)."""
    cores = os.cpu_count() or 4
    return max(1, int(cores * 0.875))


def detect_ram_gb():
    """Detect total RAM in GB from /proc/meminfo."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024)
    except:
        pass
    return 12  # fallback


def auto_context(ram_gb):
    """Auto-select context size based on available RAM."""
    if ram_gb <= 8:
        return 8192
    elif ram_gb <= 16:
        return 32768  # 12-16 GB → 32K
    else:
        return 65536


def clear():
    os.system("clear" if os.name == "posix" else "cls")


def print_box(title, lines):
    """Print a bordered menu box, centered on screen."""
    width = max(len(l) for l in lines + [title]) + 4
    try:
        cols, rows = os.get_terminal_size()
    except OSError:
        cols, rows = 80, 24
    hpad = max(0, (cols - width) // 2)
    vpad = max(0, (rows - (3 + len(lines))) // 2)
    if vpad:
        print("\n" * vpad, end="")
    pad = " " * hpad
    print(pad + "╔" + "═" * (width - 2) + "╗")
    print(pad + f"║  {title}{' ' * (width - 4 - len(title))}║")
    print(pad + "╠" + "═" * (width - 2) + "╣")
    for l in lines:
        print(pad + f"║  {l}{' ' * (width - 4 - len(l))}║")
    print(pad + "╚" + "═" * (width - 2) + "╝")


def input_key(label):
    """Read API key once (visible for paste compatibility)."""
    k = input(f"  {label}: ").strip()
    return k if k else None


def select_provider_and_model():
    """Show provider selection submenu. Returns (provider, model)."""
    providers = [
        {
            "name": "DeepSeek",
            "models": [
                ("deepseek-v4-flash", "deepseek-v4-flash - rápido y barato"),
                ("deepseek-v4-pro", "deepseek-v4-pro - razonamiento profundo"),
            ],
            "env": "DEEPSEEK_API_KEY",
            "context_limit": 1048576,
        },
        {
            "name": "OpenAI",
            "models": [
                ("gpt-4o", "gpt-4o - calidad máxima"),
                ("gpt-4o-mini", "gpt-4o-mini - económico"),
            ],
            "env": "OPENAI_API_KEY",
            "context_limit": 128000,
        },
        {
            "name": "Anthropic",
            "models": [
                ("claude-sonnet-4", "claude-sonnet-4 - equilibrio"),
                ("claude-haiku-3.5", "claude-haiku-3.5 - rápido"),
            ],
            "env": "ANTHROPIC_API_KEY",
            "context_limit": 200000,
        },
        {
            "name": "Google Gemini",
            "models": [
                ("gemini-2.0-flash", "gemini-2.0-flash - rápido"),
                ("gemini-2.0-pro", "gemini-2.0-pro - calidad"),
            ],
            "env": "GOOGLE_API_KEY",
            "context_limit": 1048576,
        },
        {
            "name": "Kimi / Moonshot",
            "models": [
                ("kimi-k2.7-code", "kimi-k2.7-code - código"),
                ("kimi-k2.7-thinking", "kimi-k2.7-thinking - razonamiento"),
            ],
            "env": "KIMI_API_KEY",
            "context_limit": 128000,
        },
        {
            "name": "Ollama Cloud",
            "models": [
                ("kimi-k2.7-code", "kimi-k2.7-code - código y ejecución"),
                ("kimi-k2.7-thinking", "kimi-k2.7-thinking - razonamiento"),
            ],
            "env": "OLLAMA_CLOUD_API_KEY",
            "context_limit": 128000,
        },
        {
            "name": "OpenRouter",
            "models": [],
            "env": "OPENROUTER_API_KEY",
            "context_limit": 128000,
        },
    ]

    while True:
        clear()
        print_box("PROVIDER", [
            "",
        ] + [
            f"  {i+1}) {p['name']}"
            for i, p in enumerate(providers)
        ] + [
            "",
            "  8) Back",
            "",
        ])
        try:
            opt = int(input("  Select (1-8): "))
        except ValueError:
            return

        if opt == 8:
            return None, None
        if opt < 1 or opt > 7:
            return

        prov = providers[opt - 1]

        # OpenRouter: free input
        if prov["name"] == "OpenRouter":
            clear()
            print_box("OPENROUTER", ["", "  Enter the model name:", "  e.g. deepseek/deepseek-v4-flash, openai/gpt-4o", ""])
            model = input("  Model: ").strip()
            if not model:
                return
            return prov, model

        # Other providers: select model
        clear()
        print_box(prov["name"], [""] + [f"  {chr(97+i)}) {m[1]}" for i, m in enumerate(prov["models"])] + ["", "  q) Back", ""])
        opt2 = input("  Select (a-b, q): ").strip().lower()

        if opt2 == "q":
            return

        idx = ord(opt2) - 97
        if idx < 0 or idx >= len(prov["models"]):
            return

        return prov, prov["models"][idx][0]


def main():
    # Check if already configured
    if CONFIG_FILE.exists():
        print(f"\n  Configuración ya existe en {CONFIG_FILE}")
        print("  Bórrala si quieres reconfigurar: rm ~/.aios/config.yaml")
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    clear()
    print_box("AIOS AGENT - INITIAL SETUP", [
        "",
        f"  Detected: {detect_cpu()} CPU threads, {detect_ram_gb()} GB RAM -> {auto_context(detect_ram_gb())//1024}K context",
        "",
        "  Choose how to use the agent:",
        "",
        "  1) LOCAL (no internet) / Simple tasks",
        "     Qwen-3-8B-Instruct",
        "     CPU: x86_64, 4+ cores",
        "     RAM: 12 GB minimum, 16 GB recommended",
        "     Context: {auto_context(detect_ram_gb())//1024}K tokens auto",
        "     Disk: 5 GB free",
        "",
        "  2) CLOUD (internet required)",
        "     Uses an external model via API",
        "     Requires an API key from a provider",
        "",
        "  3) HYBRID (local + cloud)",
        "",
        "  4) INSTALL TO DISK",
        "     Simple tasks -> local model",
        "     Complex tasks -> cloud model",
        "     Requires an API key from a provider",
        "",
    ])
    try:
        mode = int(input("  Select (1-4): "))
    except ValueError:
        mode = 0

    LOCAL_MODELS = [
        {
            "name": "Qwen3-8B-Instruct",
            "file": "Qwen_Qwen3-8B-Q4_K_M.gguf",
            "size": "4.7 GB",
            "speed": "17 tok/s",
            "desc": "most reliable",
            "default": True,
        },
    ]


    if mode not in (1, 2, 3, 4):
        print("\n  Invalid option. Defaulting to LOCAL mode.")

    if mode == 4:
        import subprocess as _sp
        ret = _sp.run(["sudo", "aios-install"])
        if ret.returncode != 0:
            print("\n  Installation aborted or failed.")
            input("  Press Enter to return to menu...")
            return
        print()
        again = input("  Reboot now? (y/N): ").strip().lower()
        if again == "y":
            _sp.run(["sudo", "reboot"])
        return

        mode = 1

    selected = LOCAL_MODELS[0]  # default, may be overridden for local
    if mode == 1:
        selected = LOCAL_MODELS[0]
        model_path = Path(f"/home/aios/.aios/models/{selected['file']}")
        if not model_path.exists():
            print(f"\n  Model {selected['file']} not found.")
            print("  Add it to the ISO or place it at {model_path}")
            print("  Continuing with cloud mode fallback.\n")
            return  # back to main menu
        else:
            print(f"\n  Model: {selected['name']} ({selected['size']})")

    ram_gb = detect_ram_gb()
    ctx = auto_context(ram_gb)

    config = {
        "mode": {1: "local", 2: "cloud", 3: "hybrid", 4: "install"}[mode],
        "local": {
            "model": selected["file"] if mode == 1 and selected else "Qwen_Qwen3-8B-Q4_K_M.gguf",
            "model_name": selected["name"] if mode == 1 and selected else "Qwen3-8B-Instruct",
            "threads": detect_cpu(),
            "context": ctx,
        },
        "cloud": {
            "provider": None,
            "model": None,
            "api_key": None,
        },
    }

    if mode in (2, 3):
        clear()
        prov_data, model = select_provider_and_model()
        if prov_data and model:
            config["cloud"]["provider"] = prov_data["name"]
            config["cloud"]["model"] = model
            config["cloud"]["context_limit"] = prov_data.get("context_limit", 128000)
            while True:
                clear()
                print_box("API KEY", ["", "  Enter your API key (or leave empty to cancel).", ""])
                key = input_key("  API Key")
                if not key:
                    print("\n  No API key provided. Defaulting to LOCAL mode.\n")
                    config["mode"] = "local"
                    break
                config["cloud"]["api_key"] = key
                print("  Testing API key...", flush=True)
                valid = validate_api_key(prov_data["name"], key)
                if valid is True:
                    print("  API key is valid.", flush=True)
                    break
                elif valid is False:
                    print("\n  Invalid API key. Check and try again.\n")
                    input("  Press Enter to retry...")
                    continue
                else:
                    # Could not verify (network issue)
                    retry = input("  (Could not verify API key. Use anyway? (Y/n): ").strip().lower()
                    if retry != "n":
                        break
                    continue
            if key:
                env_var = {
                    "DeepSeek": "DEEPSEEK_API_KEY",
                    "OpenAI": "OPENAI_API_KEY",
                    "Anthropic": "ANTHROPIC_API_KEY",
                    "Google Gemini": "GOOGLE_API_KEY",
                    "Kimi / Moonshot": "KIMI_API_KEY",
                    "Ollama Cloud": "OLLAMA_CLOUD_API_KEY",
                    "OpenRouter": "OPENROUTER_API_KEY",
                }.get(prov_data["name"], "API_KEY")
                # Save to .env instead of config.yaml
                env_path = CONFIG_DIR / ".env"
                # Load existing env vars, update or add the new one
                env_lines = []
                if env_path.exists():
                    with open(env_path) as f:
                        for line in f:
                            if not line.startswith(f"{env_var}="):
                                env_lines.append(line)
                env_lines.append(f"{env_var}={key}\n")
                with open(env_path, "w") as f:
                    f.writelines(env_lines)
                print(f"  API key saved to {env_path}", flush=True)
                del config["cloud"]["api_key"]  # remove from yaml
        else:
            # User went back, fallback to local
            config["mode"] = "local"

    # Save config
    import yaml
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    # Enable llama service if local or hybrid mode
    import subprocess as _sp
    if config.get("mode") in ("local", "hybrid"):
        _sp.run(["systemctl", "enable", "aios-llama.service"], capture_output=True)
        _sp.run(["systemctl", "start", "aios-llama.service"], capture_output=True)
        print("  [Service] aios-llama.service enabled and started")

    clear()
    summary = [
        "",
        f"  Mode: {config['mode']}",
    ]

    if mode == 1:
        summary.append(f"  Model: {selected['name']} ({selected['size']}, {selected['speed']})")
        summary.extend([
            f"  CPU threads: {config['local']['threads']} ({config['local']['threads']*100//os.cpu_count()}%)",
            f"  Context: {config['local']['context']} tokens",
        ])
    if config.get('cloud', {}).get('provider'):
        summary.extend([
            f"  Cloud: {config['cloud']['provider']}",
            f"  Model: {config['cloud']['model']}",
            f"  API Key: {'saved' if config['cloud'].get('api_key') else 'not configured'}",
        ])
    summary += [
        "",
        f"  Saved to: {CONFIG_FILE}",
        "",
        "  Setup complete. Starting the AIOS agent...",
        "",
    ]
    print_box("SETUP COMPLETE", summary)


if __name__ == "__main__":
    while True:
        try:
            main()
            # If we get here and config exists, setup was successful
            if CONFIG_FILE.exists():
                break
            # main() returned early (download failed, etc.)
            retry = input("\n  Back to main menu? (Y/n): ").strip().lower()
            if retry == "n":
                break
            import sys
            print("\033[2J\033[H", end="")
        except KeyboardInterrupt:
            print("\n  Exiting.")
            break
        except Exception as e:
            print(f"\n  Error: {e}")
            retry = input("  Try again? (Y/n): ").strip().lower()
            if retry == "n":
                break
            print("\033[2J\033[H", end="")

    # Salida forzada: no esperar hilos residuales (p.ej. validación DNS colgada)
    os._exit(0)
