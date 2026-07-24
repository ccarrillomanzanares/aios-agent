"""AIOS Agent - Configuration setup (first-run wizard)."""
import json
import os
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
    """Print a bordered menu box."""
    width = max(len(l) for l in lines + [title]) + 4
    print("╔" + "═" * (width - 2) + "╗")
    print(f"║  {title}{' ' * (width - 4 - len(title))}║")
    print("╠" + "═" * (width - 2) + "╣")
    for l in lines:
        print(f"║  {l}{' ' * (width - 4 - len(l))}║")
    print("╚" + "═" * (width - 2) + "╝")


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
            continue

        if opt == 8:
            return None, None
        if opt < 1 or opt > 7:
            continue

        prov = providers[opt - 1]

        # OpenRouter: free input
        if prov["name"] == "OpenRouter":
            clear()
            print_box("OPENROUTER", ["", "  Enter the model name:", "  e.g. deepseek/deepseek-v4-flash, openai/gpt-4o", ""])
            model = input("  Model: ").strip()
            if not model:
                continue
            return prov, model

        # Other providers: select model
        clear()
        print_box(prov["name"], [""] + [f"  {chr(97+i)}) {m[1]}" for i, m in enumerate(prov["models"])] + ["", "  q) Back", ""])
        opt2 = input("  Select (a-b, q): ").strip().lower()

        if opt2 == "q":
            continue

        idx = ord(opt2) - 97
        if idx < 0 or idx >= len(prov["models"]):
            continue

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
        "  1) LOCAL (no internet) [RECOMMENDED]",
        "     Qwen2.5-7B-Incluided in ISO",
        "     CPU: x86_64, 4+ cores",
        "     RAM: 12 GB minimum, 16 GB recommended",
        "     Context: {auto_context(detect_ram_gb())//1024}K tokens auto",
        "     Disk: 5 GB free",
        "     Works 100% offline",
        "",
        "  2) CLOUD (internet required)",
        "     Uses an external model via API",
        "     Requires an API key from a provider",
        "",
        "  3) HYBRID (local + cloud)",
        "     Simple tasks -> local model",
        "     Complex tasks -> cloud model",
        "     Requires an API key from a provider",
        "",
    ])
    try:
        mode = int(input("  Select (1-3): "))
    except ValueError:
        mode = 0

    LOCAL_MODELS = [
        {
            "name": "Qwen3-8B-Instruct",
            "file": "Qwen_Qwen3-8B-Q4_K_M.gguf",
            "repo": "bartowski/Qwen_Qwen3-8B-GGUF",
            "size": "4.7 GB",
            "speed": "17 tok/s",
            "desc": "most reliable",
            "default": True,
        },
        {
            "name": "Qwen2.5-7B-Instruct",
            "file": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
            "repo": "bartowski/Qwen2.5-7B-Instruct-GGUF",
            "size": "4.4 GB",
            "speed": "20 tok/s",
            "desc": "faster",
            "default": False,
        },
    ]


    if mode not in (1, 2, 3):
        print("\n  Invalid option. Defaulting to LOCAL mode.")
        mode = 1

    selected = LOCAL_MODELS[0]  # default, may be overridden for local
    if mode == 1:
        clear()
        print_box("LOCAL MODEL", [
            "",
        ] + [
            f"  {i+1}) {m['name']} ({m['size']}, {m['speed']}) - {m['desc']}" + (" [DEFAULT]" if m["default"] else "")
            for i, m in enumerate(LOCAL_MODELS)
        ] + [
            "",
            f"  Default: 1) {LOCAL_MODELS[0]['name']}",
            "",
        ])
        try:
            model_opt = int(input("  Select (1-2): "))
        except ValueError:
            model_opt = 1
        if model_opt < 1 or model_opt > 2:
            model_opt = 1
        selected = LOCAL_MODELS[model_opt - 1]
        model_path = Path(f"/home/ccmai/models/{selected['file']}")
        if not model_path.exists():
            print(f"\n  Model {selected['file']} not found locally.")
            dl = input("  Download from HuggingFace? (Y/n): ").strip().lower()
            if dl != "n":
                print(f"  Downloading {selected['name']} ({selected['size']})...")
                from huggingface_hub import hf_hub_download
                hf_hub_download(selected["repo"], selected["file"], local_dir="/home/ccmai/models/")
                print("  Download complete.")
        else:
            print(f"\n  Model found at {model_path}")

    ram_gb = detect_ram_gb()
    ctx = auto_context(ram_gb)

    config = {
        "mode": {1: "local", 2: "cloud", 3: "hybrid"}[mode],
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
            clear()
            print_box("API KEY", ["", "  Enter your API key.", ""])
            key = input_key("  API Key")
            config["cloud"]["api_key"] = key
            if not key:
                print("\n  No API key provided. Defaulting to LOCAL mode.\n")
                config["mode"] = "local"
            else:
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
                print(f"  API key saved to {env_path}")
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
    if mode == 1:
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
        "  Ready! Run 'python3 chat.py' to start.",
        "",
    ]
    print_box("SETUP COMPLETE", summary)


if __name__ == "__main__":
    main()
