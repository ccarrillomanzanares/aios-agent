#!/usr/bin/env python3
"""Interactive chat with the SRE Agent.
Loads config from ~/.aios/config.yaml on first run.
Supports local, cloud, and hybrid modes."""
import os
import sys
import readline
import atexit
from pathlib import Path

CONFIG_FILE = Path.home() / ".aios" / "config.yaml"

# Provider → API endpoint mapping
CLOUD_ENDPOINTS = {
    "DeepSeek": "https://api.deepseek.com/v1/chat/completions",
    "OpenAI": "https://api.openai.com/v1/chat/completions",
    "Anthropic": "https://api.anthropic.com/v1/chat/completions",
    "Google Gemini": "https://generativelanguage.googleapis.com/v1beta",
    "Kimi / Moonshot": "https://api.moonshot.cn/v1/chat/completions",
    "Ollama Cloud": "https://api.ollama.cloud/v1/chat/completions",
    "OpenRouter": "https://openrouter.ai/api/v1/chat/completions",
}


def load_or_setup():
    """Load config or run first-run setup."""
    if not CONFIG_FILE.exists():
        print("\n  [First run] Running initial setup wizard...\n")
        import setup
        setup.main()
        print()

    import yaml
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def main():
    config = load_or_setup()
    mode = config.get("mode", "local")

    # Setup history
    history_file = Path("data/.chat_history")
    history_file.parent.mkdir(parents=True, exist_ok=True)
    if history_file.exists():
        readline.read_history_file(str(history_file))
    readline.set_history_length(500)
    atexit.register(lambda: readline.write_history_file(str(history_file)))

    # Configure agent based on mode
    if mode == "local":
        os.environ["AIOS_MODE"] = "local"
        os.environ["AIOS_LLAMA_SERVER"] = "http://localhost:8083/v1/chat/completions"
    elif mode == "cloud":
        os.environ["AIOS_MODE"] = "cloud"
        provider = config.get("cloud", {}).get("provider")
        model = config.get("cloud", {}).get("model")
        api_key = config.get("cloud", {}).get("api_key")
        ctx = config.get("cloud", {}).get("context_limit", 128000)
        endpoint = CLOUD_ENDPOINTS.get(provider, "https://api.deepseek.com/v1")
        os.environ["AIOS_LLAMA_SERVER"] = endpoint
        os.environ["AIOS_API_KEY"] = api_key or ""
        os.environ["AIOS_CLOUD_MODEL"] = model or "deepseek-chat"
        os.environ["AIOS_CLOUD_CONTEXT"] = str(ctx)
        # Set provider-specific env var
        env_var = config.get("cloud", {}).get("provider_env", "")
        if env_var and api_key:
            os.environ[env_var] = api_key
    elif mode == "hybrid":
        os.environ["AIOS_MODE"] = "hybrid"
        os.environ["AIOS_LLAMA_SERVER"] = "http://localhost:8083/v1/chat/completions"
        provider = config.get("cloud", {}).get("provider")
        model = config.get("cloud", {}).get("model")
        api_key = config.get("cloud", {}).get("api_key")
        ctx = config.get("cloud", {}).get("context_limit", 128000)
        if provider and api_key:
            os.environ["AIOS_CLOUD_PROVIDER"] = provider
            os.environ["AIOS_CLOUD_MODEL"] = model or "deepseek-chat"
            os.environ["AIOS_CLOUD_CONTEXT"] = str(ctx)
            os.environ["AIOS_CLOUD_ENDPOINT"] = CLOUD_ENDPOINTS.get(provider, "")
            os.environ["AIOS_API_KEY"] = api_key
            env_var = config.get("cloud", {}).get("provider_env", "")
            if env_var:
                os.environ[env_var] = api_key

    from agent import Agent

    agent = Agent()
    mode_label = {"local": "LOCAL", "cloud": "CLOUD", "hybrid": "HIBRIDO"}.get(mode, "LOCAL")
    if mode == "local":
        print(f"  [{mode_label}] Qwen2.5-7B-Instruct (~20 tok/s, {config['local']['threads']}/{os.cpu_count()} cores)")
    elif mode == "cloud":
        prov = config.get("cloud", {}).get("provider", "?")
        mod = config.get("cloud", {}).get("model", "?")
        print(f"  [{mode_label}] {prov}: {mod}")
    else:  # hybrid
        prov = config.get("cloud", {}).get("provider", "?")
        mod = config.get("cloud", {}).get("model", "?")
        print(f"  [{mode_label}] Local + {prov}: {mod}")
    print(f"  [{mode_label}] Sesión independiente por modo (no se comparte contexto entre modos)")
    print("  Escribe tu consulta o 'salir'.\n")

    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            agent._save_session()
            print("\n¡Hasta luego!")
            break

        if not query:
            continue
        if query.lower() in ("salir", "exit", "quit"):
            agent._save_session()
            print("¡Hasta luego!")
            break

        try:
            response = agent.run(query)
            print(f"\n{response}\n")
        except KeyboardInterrupt:
            print("\n[Interrumpido]")
            continue


if __name__ == "__main__":
    main()
