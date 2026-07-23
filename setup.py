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
    """Read API key with double verification."""
    while True:
        k1 = input(f"  {label}: ").strip()
        if not k1:
            print("  [!] La clave no puede estar vacía.")
            continue
        k2 = input(f"  Confirma: ").strip()
        if k1 == k2:
            return k1
        print("  [!] Las claves no coinciden. Intenta de nuevo.")


def select_provider_and_model():
    """Show provider selection submenu. Returns (provider, model)."""
    providers = [
        {
            "name": "DeepSeek",
            "models": [
                ("deepseek-chat", "deepseek-chat - rápido y barato"),
                ("deepseek-reasoner", "deepseek-reasoner - razonamiento profundo"),
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
            "name": "OpenRouter",
            "models": [],
            "env": "OPENROUTER_API_KEY",
        },
    ]

    while True:
        clear()
        print_box("PROVEEDOR CLOUD", [
            "",
        ] + [
            f"  {i+1}) {p['name']}"
            for i, p in enumerate(providers)
        ] + [
            "",
            "  7) Volver",
            "",
        ])
        try:
            opt = int(input("  Selecciona (1-7): "))
        except ValueError:
            continue

        if opt == 7:
            return None, None
        if opt < 1 or opt > 6:
            continue

        prov = providers[opt - 1]

        # OpenRouter: free input
        if prov["name"] == "OpenRouter":
            clear()
            print_box("OPENROUTER", ["", "  Introduce el nombre del modelo:", "  ej: openai/gpt-4o, anthropic/claude-sonnet-4", ""])
            model = input("  Modelo: ").strip()
            if not model:
                continue
            return prov["name"], model

        # Other providers: select model
        clear()
        print_box(prov["name"], [""] + [f"  {chr(97+i)}) {m[1]}" for i, m in enumerate(prov["models"])] + ["", "  q) Volver", ""])
        opt2 = input("  Selecciona (a-b, q): ").strip().lower()

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
    print_box("AIOS AGENT - CONFIGURACIÓN INICIAL", [
        "",
        "  Elige cómo quieres usar el agente:",
        "",
        "  1) LOCAL (sin internet) [RECOMENDADO]",
        "     Qwen2.5-7B-Incluido en la ISO",
        "     CPU: x86_64, 4+ cores",
        "     RAM: 8 GB mínimo, 12 GB recomendado",
        "     Disco: 5 GB libres",
        "     Funciona 100% offline",
        "",
        "  2) CLOUD (solo internet)",
        "     El agente usa un modelo externo vía API",
        "     Necesitas API key del proveedor",
        "",
        "  3) HÍBRIDO (local + cloud)",
        "     Simple -> modelo local",
        "     Complejo -> modelo cloud",
        "     Necesitas API key del proveedor",
        "",
    ])
    try:
        mode = int(input("  Selecciona (1-3): "))
    except ValueError:
        mode = 0

    if mode not in (1, 2, 3):
        print("\n  Opción inválida. Usando modo LOCAL por defecto.")
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
            print_box("API KEY", ["", "  Introduce tu clave de API.", "  Se verificará dos veces.", ""])
            key = input_key("  API Key")
            config["cloud"]["api_key"] = key
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
    print_box("CONFIGURACIÓN COMPLETA", [
        "",
        f"  Modo: {config['mode']}",
        f"  CPUs: {config['local']['threads']} threads ({detect_cpu()*100//os.cpu_count()}%)",
        f"  Contexto: {config['local']['context']} tokens",
    ] + ([
        f"  Cloud: {config['cloud']['provider']}",
        f"  Modelo: {config['cloud']['model']}",
        f"  API Key: {'✓ guardada' if config['cloud'].get('api_key') else '✗ no configurada'}",
    ] if config.get('cloud', {}).get('provider') else []) + [
        "",
        f"  Guardado en: {CONFIG_FILE}",
        "",
        "  ¡Listo! Ejecuta 'python3 chat.py' para empezar.",
        "",
    ])


if __name__ == "__main__":
    main()
