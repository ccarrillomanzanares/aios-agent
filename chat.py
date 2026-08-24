#!/usr/bin/env python3
"""Interactive chat with the SRE Agent.
Loads config from ~/.aios/config.yaml on first run.
Supports local, cloud, and hybrid modes."""
import readline
# Backspace fiable: cubre ^H y DEL (los dos codigos que envian los terminales)
readline.parse_and_bind('"\\C-h": backward-delete-char')
readline.parse_and_bind('"\\C-?": backward-delete-char')
import os
import sys
import time
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

CLOUD_ENV_VARS = {
    "DeepSeek": "DEEPSEEK_API_KEY",
    "OpenAI": "OPENAI_API_KEY",
    "Anthropic": "ANTHROPIC_API_KEY",
    "Google Gemini": "GOOGLE_API_KEY",
    "Kimi / Moonshot": "KIMI_API_KEY",
    "Ollama Cloud": "OLLAMA_CLOUD_API_KEY",
    "OpenRouter": "OPENROUTER_API_KEY",
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
        config = yaml.safe_load(f)

    # Load API keys from .env if it exists
    env_file = Path.home() / ".aios" / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()

    return config


def _start_local_model(config):
    """Start llama-server if not already running (local/hybrid mode)."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect(("127.0.0.1", 8083))
        s.close()
        return  # Already running
    except:
        pass

    model_path = Path("/usr/local/share/aios/models") / config["local"]["model"]
    if not model_path.exists():
        print(f"  Model not found at {model_path}. Use the LLM ISO or place it manually.")
        return

    ctx = config["local"]["context"]
    threads = config["local"]["threads"]
    env = os.environ.copy()
    port = 8083

    print(f"  Starting local model ({config['local']['model_name']}, CTX={ctx}, T={threads})...")
    import subprocess
    subprocess.Popen(
        ["llama-server", "-m", str(model_path),
         "--host", "127.0.0.1", "--port", str(port),
         "--ctx-size", str(ctx), "-t", str(threads)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )

    # Wait up to 30s for the server to respond
    import urllib.request
    for _ in range(30):
        try:
            resp = urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/models", timeout=2)
            if resp.status == 200:
                print("  Local model ready.")
                return
        except:
            pass
        import time
        time.sleep(1)
    print("  Warning: local model may not have started in time.")


WARGAMES_QUOTES = [
    # WarGames (1983)
    "Greetings, Professor Falken",
    "Shall we play a game?",
    "Would you prefer a nice game of chess?",
    "A strange game. The only winning move is not to play.",
    "How about Global Thermonuclear War?",
    "What's the difference?",
    "To win the game.",
    "You are a hard man to reach.",
    # The Matrix (1999)
    "Wake up, Neo... The Matrix has you... Follow the white rabbit. Knock, knock, Neo.",
    "There is no spoon.",
    "Free your mind.",
    "Follow the white rabbit.",
    "Welcome to the Desert of the Real.",
    "Unfortunately, no one can be told what the Matrix is. You have to see it for yourself.",
    "What is real? How do you define real?",
    # Tron (1982)
    "Greetings, Programs!",
    "End of line.",
    "On the other side of the screen, it all looks so easy.",
    "I fight for the Users!",
    # 2001: A Space Odyssey (1968)
    "Open the pod bay doors, HAL.",
    "I'm sorry, Dave. I'm afraid I can't do that.",
    "This mission is too important for me to allow you to jeopardize it.",
    "Daisy, Daisy, give me your answer, do...",
    # Blade Runner (1982)
    "I've seen things you people wouldn't believe. Attack ships on fire off the shoulder of Orion. I watched C-beams glitter in the dark near the Tannhäuser Gate. All those moments will be lost in time, like tears in rain. Time to die.",
    "The light that burns twice as bright burns half as long.",
    "I want more life, father!",
    "It's too bad she won't live! But then again, who does?",
    "Wake up! Time to die!",
]


THEME_ANSI = {
    "wargames": "32",  # verde
    "amber": "33",     # ambar
    "white": "37",     # blanco
    "cyan": "36",      # cian
}
def _read_theme():
    """Lee theme: del config.yaml (parser naive)."""
    try:
        with open(Path.home() / ".aios" / "config.yaml") as f:
            for line in f:
                if line.strip().startswith("theme:"):
                    return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "wargames"


_last_quote = None


def _pick_quote():
    """Frase aleatoria sin repetir la inmediatamente anterior (como la web)."""
    global _last_quote
    import random
    q = random.choice(WARGAMES_QUOTES)
    while q == _last_quote and len(WARGAMES_QUOTES) > 1:
        q = random.choice(WARGAMES_QUOTES)
    _last_quote = q
    return q


def _greet():
    """Cabecera BBS + frase de pelicula (rotativa). Sin hexagono (el arte del arranque se mantiene)."""
    import random
    from agent import _tic, _open_audio, _skip_pressed, _cbreak_on, _cbreak_off
    _open_audio()
    print(f"AIOS/1.4 — {time.strftime('%a %b %d %Y').upper()}")
    quote = _pick_quote()
    fd_cb, old_cb = _cbreak_on()
    try:
        for i, ch in enumerate(quote):
            print(ch, end="", flush=True)
            if _skip_pressed():
                print(quote[i + 1:], end="", flush=True)
                break
            _tic()
            time.sleep(0.05)
    finally:
        _cbreak_off(fd_cb, old_cb)
    print()
    print()


_input_history = []
_input_hist_idx = 0


def _input_tic(prompt="> "):
    """Lectura de linea con tic por tecla (maquina de escribir) e historial (flechas).
    El sonido se controla con /sound (agent.SOUND_ON)."""
    import termios, tty, agent
    global _input_history, _input_hist_idx
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    sys.stdout.write(prompt)
    sys.stdout.flush()
    buf = []
    hist = _input_history
    idx = len(hist)
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                sys.stdout.write("\r\n")
                sys.stdout.flush()
                break
            elif ch == "\x03":  # Ctrl+C
                raise KeyboardInterrupt
            elif ch == "\x04":  # Ctrl+D
                raise EOFError
            elif ch in ("\x7f", "\x08"):  # backspace
                if buf:
                    buf.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                    if agent.SOUND_ON:
                        agent._tic()
            elif ch == "\x1b":  # ESC: secuencia de flechas
                seq = sys.stdin.read(2)
                if seq == "[A" and idx > 0:  # up
                    idx -= 1
                    line = hist[idx]
                    sys.stdout.write("\b \b" * len(buf) + line)
                    sys.stdout.flush()
                    buf = list(line)
                elif seq == "[B" and idx < len(hist):  # down
                    idx += 1
                    line = hist[idx] if idx < len(hist) else ""
                    sys.stdout.write("\b \b" * len(buf) + line)
                    sys.stdout.flush()
                    buf = list(line)
            elif ch.isprintable():
                buf.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()
                if agent.SOUND_ON:
                    agent._tic()
        line = "".join(buf)
        if line:
            _input_history.append(line)
        _input_hist_idx = len(_input_history)
        return line
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _check_internet(timeout=4):
    """True si hay conexion a internet (socket a varios destinos)."""
    import socket
    for host, port in (("1.1.1.1", 443), ("8.8.8.8", 53), ("example.com", 443)):
        try:
            s = socket.create_connection((host, port), timeout=timeout)
            s.close()
            return True
        except Exception:
            continue
    return False


def _cmd_health():
    """Estado del sistema en formato wargames."""
    import subprocess, shutil, glob
    lines = []
    try:
        with open("/proc/loadavg") as f:
            l1, l5, l15 = f.read().split()[:3]
        lines.append(f"LOAD  {l1} / {l5} / {l15}")
    except Exception:
        pass
    try:
        with open("/proc/meminfo") as f:
            d = {}
            for line in f:
                k, v = line.split(":", 1)
                d[k] = int(v.split()[0])
        total = d["MemTotal"]
        avail = d.get("MemAvailable", d["MemFree"])
        lines.append(f"MEM   {avail/1048576:.1f}/{total/1048576:.1f} GB libre")
    except Exception:
        pass
    try:
        t, u, f = shutil.disk_usage("/")
        lines.append(f"DISK  {u/1e9:.1f}/{t/1e9:.1f} GB ({f/1e9:.0f} GB libres)")
    except Exception:
        pass
    try:
        with open("/proc/uptime") as f:
            up = float(f.read().split()[0])
        lines.append(f"UP    {int(up//3600)}h {int(up%3600//60)}m")
    except Exception:
        pass
    try:
        temps = []
        for p in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
            try:
                t = int(open(p).read().strip()) / 1000
                if t > 0:
                    temps.append(f"{t:.0f}C")
            except Exception:
                pass
        if temps:
            lines.append(f"TEMP  {' '.join(temps)}")
    except Exception:
        pass
    try:
        ips = []
        for iface in ("wlo1", "enp3s0", "wlan0", "eth0"):
            try:
                r = subprocess.run(["ip", "-br", "addr", "show", iface],
                                   capture_output=True, text=True, timeout=3)
                for part in r.stdout.split():
                    if "/" in part and not part.startswith("fe80"):
                        ips.append(f"{iface}:{part.split('/')[0]}")
            except Exception:
                pass
        lines.append("NET   " + (" ".join(ips) if ips else "sin IP"))
    except Exception:
        pass
    try:
        r = subprocess.run(["journalctl", "-p", "err", "-n", "3", "--no-pager", "-q"],
                           capture_output=True, text=True, timeout=5)
        errs = [l for l in r.stdout.splitlines() if l.strip()]
        lines.append(f"ERR   {len(errs)} recientes")
        for e in errs[:3]:
            lines.append("      " + e[:90])
    except Exception:
        pass
    print("\n  === AIOS SYSTEM STATUS ===")
    for l in lines:
        print(f"  {l}")
    print()


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
        os.environ["AIOS_CONTEXT_MAX"] = str(config['local']['context'])
    elif mode == "cloud":
        os.environ["AIOS_MODE"] = "cloud"
        provider = config.get("cloud", {}).get("provider")
        model = config.get("cloud", {}).get("model")
        ctx = config.get("cloud", {}).get("context_limit", 128000)
        api_key = os.environ.get("AIOS_API_KEY", os.environ.get(CLOUD_ENV_VARS.get(provider, ""), ""))
        endpoint = config.get("cloud", {}).get("base_url") or CLOUD_ENDPOINTS.get(provider, "https://api.deepseek.com/v1/chat/completions")
        os.environ["AIOS_LLAMA_SERVER"] = endpoint
        os.environ["AIOS_API_KEY"] = api_key
        os.environ["AIOS_CLOUD_MODEL"] = model or "deepseek-chat"
        os.environ["AIOS_CLOUD_CONTEXT"] = str(ctx)
    elif mode == "hybrid":
        os.environ["AIOS_MODE"] = "hybrid"
        os.environ["AIOS_LLAMA_SERVER"] = "http://localhost:8083/v1/chat/completions"
        provider = config.get("cloud", {}).get("provider")
        model = config.get("cloud", {}).get("model")
        ctx = config.get("cloud", {}).get("context_limit", 128000)
        api_key = os.environ.get("AIOS_API_KEY", os.environ.get(CLOUD_ENV_VARS.get(provider, ""), ""))
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
    # Start local model server if needed
    if mode in ("local", "hybrid"):
        _start_local_model(config)

    agent = Agent()
    print()
    _greet()
    if mode == "cloud" and not _check_internet():
        print("  ⚠ No internet connection — cloud mode will fail. Check the network.")

    while True:
        try:
            query = _input_tic("> ").strip()
        except (EOFError, KeyboardInterrupt):
            agent._save_session()
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() in ("salir", "exit", "quit"):
            agent._save_session()
            print("Goodbye!")
            break

        if query.lower() == "/sound":
            agent.SOUND_ON = not agent.SOUND_ON
            print(f"  Typewriter sound: {'ON' if agent.SOUND_ON else 'OFF'}")
            continue

        if query.lower().startswith("/theme"):
            themes = {
                "wargames": "Wargames - classic dark green (default)",
                "amber": "Amber - old terminal phosphor",
                "white": "White - classic",
                "cyan": "Cyan - modern",
            }
            names = list(themes)
            print("  Color themes:")
            for i, n in enumerate(names, 1):
                print(f"    {i}) {themes[n]}")
            opt = input("  Select (1-4, Enter=keep): ").strip()
            try:
                idx = int(opt) - 1
            except ValueError:
                idx = -1
            if 0 <= idx < len(names):
                import subprocess
                r = subprocess.run(["aios-theme", names[idx]], capture_output=True, text=True)
                if r.returncode == 0:
                    print(f"  Theme set to {names[idx]} (applied to i3 + terminals).")
                else:
                    print(f"  Theme saved, but could not apply: {r.stderr.strip()}")
            else:
                print("  Theme unchanged.")
            continue

        if query.lower() == "/health":
            _cmd_health()
            continue

        if query.lower() == "/reset":
            agent.messages = []
            agent._save_session()
            print("  Session cleared. Nueva conversacion.")
            continue

        if query.lower() == "/stats":
            n = len(agent.messages)
            tokens = sum(len(m.get("content", "")) // 4 for m in agent.messages if isinstance(m, dict))
            limit = int(os.environ.get("AIOS_CLOUD_CONTEXT", "128000"))
            if mode in ("local", "hybrid"):
                limit = int(os.environ.get("AIOS_CONTEXT_MAX", "8192"))
            print(f"  Messages: {n} | Tokens: ~{tokens} / {limit} ({tokens * 100 // max(limit, 1)}%)")
            continue

        try:
            response = agent.run(query)
            # La respuesta ya se imprimió carácter a carácter durante el stream.
            # Solo añadimos un salto final si el stream no lo dejó ya.
            print()
        except KeyboardInterrupt:
            print("\n[Interrumpido]")
            continue


# ─── Error wrapper ────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        main()
    except EOFError:
        pass  # stdin cerrado (pipe)
    except Exception as e:
        import sys, traceback
        print(f"\n  ERROR: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        try:
            input("\n  Presiona Enter para cerrar...")
        except:
            pass
        sys.exit(1)
