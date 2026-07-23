"""AIOS Agent - Configuration setup (first-run wizard)."""
import json
import os
import platform
from pathlib import Path

CONFIG_DIR = Path.home() / ".aios"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


def detect_cpu():
    """Return recommended thread count (80% of cores)."""
    cores = os.cpu_count() or 4
    return max(1, int(cores * 0.8))


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
    """Read API key once."""
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
        },
        {
            "name": "OpenAI",
            "models": [
                ("gpt-4o", "gpt-4o - calidad máxima"),
                ("gpt-4o-mini", "gpt-4o-mini - económico"),
            ],
            "env": "OPENAI_API_KEY",
        },
        {
            "name": "Anthropic",
            "models": [
                ("claude-sonnet-4", "claude-sonnet-4 - equilibrio"),
                ("claude-haiku-3.5", "claude-haiku-3.5 - rápido"),
            ],
            "env": "ANTHROPIC_API_KEY",
        },
        {
            "name": "Google Gemini",
            "models": [
                ("gemini-2.0-flash", "gemini-2.0-flash - rápido"),
                ("gemini-2.0-pro", "gemini-2.0-pro - calidad"),
            ],
            "env": "GOOGLE_API_KEY",
        },
        {
            "name": "Kimi / Moonshot",
            "models": [
                ("kimi-k2.7-code", "kimi-k2.7-code - código"),
                ("kimi-k2.7-thinking", "kimi-k2.7-thinking - razonamiento"),
            ],
            "env": "KIMI_API_KEY",
        },
        {
            "name": "Ollama Cloud",
            "models": [
                ("kimi-k2.7-code", "kimi-k2.7-code - código y ejecución"),
                ("kimi-k2.7-thinking", "kimi-k2.7-thinking - razonamiento"),
            ],
            "env": "OLLAMA_CLOUD_API_KEY",
        },
        {
            "name": "OpenRouter",
            "models": [],
            "env": "OPENROUTER_API_KEY",
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
            return prov["name"], model

        # Other providers: select model
        clear()
        print_box(prov["name"], [""] + [f"  {chr(97+i)}) {m[1]}" for i, m in enumerate(prov["models"])] + ["", "  q) Back", ""])
        opt2 = input("  Select (a-b, q): ").strip().lower()

        if opt2 == "q":
            continue

        idx = ord(opt2) - 97
        if idx < 0 or idx >= len(prov["models"]):
            continue

        return prov["name"], prov["models"][idx][0]


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
        "  Choose how to use the agent:",
        "",
        "  1) LOCAL (no internet) [RECOMMENDED]",
        "     Qwen2.5-7B-Incluided in ISO",
        "     CPU: x86_64, 4+ cores",
        "     RAM: 8 GB minimum, 12 GB recommended",
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
        mode = int(input("  Selecciona (1-3): "))
    except ValueError:
        mode = 0

    if mode not in (1, 2, 3):
        print("\n  Invalid option. Defaulting to LOCAL mode.")
        mode = 1

    config = {
        "mode": {1: "local", 2: "cloud", 3: "hybrid"}[mode],
        "local": {
            "model": "Qwen2.5-7B-Instruct-Q4_K_M.gguf",
            "threads": detect_cpu(),
            "context": 8192,
        },
        "cloud": {
            "provider": None,
            "model": None,
            "api_key": None,
        },
    }

    if mode in (2, 3):
        clear()
        prov, model = select_provider_and_model()
        if prov and model:
            config["cloud"]["provider"] = prov
            config["cloud"]["model"] = model
            clear()
            print_box("API KEY", ["", "  Enter your API key.", ""])
            key = input_key("  API Key")
            config["cloud"]["api_key"] = key
            if not key:
                print("\n  No API key provided. Defaulting to LOCAL mode.\n")
                config["mode"] = "local"
            config["cloud"]["provider_env"] = {
                "DeepSeek": "DEEPSEEK_API_KEY",
                "OpenAI": "OPENAI_API_KEY",
                "Anthropic": "ANTHROPIC_API_KEY",
                "Google Gemini": "GOOGLE_API_KEY",
                "Kimi / Moonshot": "KIMI_API_KEY",
                "OpenRouter": "OPENROUTER_API_KEY",
            }.get(prov, "API_KEY")
        else:
            # User went back, fallback to local
            config["mode"] = "local"

    # Save config
    import yaml
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    clear()
    print_box("SETUP COMPLETE", [
        "",
        f"  Mode: {config['mode']}",
        f"  CPU threads: {config['local']['threads']} ({config['local']['threads']*100//os.cpu_count()}%)",
        f"  Context: {config['local']['context']} tokens",
    ] + ([
        f"  Cloud: {config['cloud']['provider']}",
        f"  Model: {config['cloud']['model']}",
        f"  API Key: {'saved' if config['cloud'].get('api_key') else 'not configured'}",
    ] if config.get('cloud', {}).get('provider') else []) + [
        "",
        f"  Saved to: {CONFIG_FILE}",
        "",
        "  Ready! Run 'python3 chat.py' to start.",
        "",
    ])


if __name__ == "__main__":
    main()
