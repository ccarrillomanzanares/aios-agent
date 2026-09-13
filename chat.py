#!/usr/bin/env python3

"""Interactive chat with the SRE Agent.

Loads config from ~/.aios/config.yaml on first run.

Supports local, cloud, and hybrid modes."""

import readline

# Reliable backspace: covers ^H and DEL (the two codes sent by terminals)

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

    except Exception:

        pass



    model_path = Path("/usr/local/share/aios/models") / config["local"]["model"]

    if not model_path.exists():

        print(f"  Model not found at {model_path}. Use the LLM ISO or place it manually.")

        return



    ctx = config["local"]["context"]

    threads = config["local"]["threads"]

    env = os.environ.copy()

    port = 8083



    print(f"  Loading local model ({config['local']['model_name']}, {ctx} ctx, {threads} threads)...")

    import subprocess, time, select

    proc = subprocess.Popen(

        # Anti-degeneration (13 Sep 2026). Without these, llama-server uses its

        # defaults and those have the repetition penalties DISABLED

        # (repeat-penalty 1.00, dry 0.00). A long repetitive generation then

        # loops: the tool call degenerates, its arguments end as invalid JSON

        # and the server answers HTTP 500 instead of a reply. Seen exactly like

        # this on the VPS with the 35B MoE, and this launcher had the same gap.

        # These cannot be set per request from the agent (repeat_penalty and

        # dry_multiplier are not OpenAI API fields), so they belong here.

        ["llama-server", "-m", str(model_path),

         "--host", "127.0.0.1", "--port", str(port),

         "-c", str(ctx), "-t", str(threads),

         "--repeat-penalty", "1.1",

         "--repeat-last-n", "256",

         "--dry-multiplier", "0.8",

         "--dry-base", "1.75",

         "--dry-allowed-length", "2",

         "--top-p", "0.9",

         "--top-k", "40",

         "--min-p", "0.05"],

        env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1

    )



    # Real progress: advances with observable llama-server startup milestones plus wall time.

    # (Not a percentage of bytes; each phase is an observable boot milestone.)

    t0 = time.time()

    label, pct = "Loading model", 10

    BAR = 22



    def _render():

        filled = int(BAR * pct / 100)

        bar = "█" * filled + "░" * (BAR - filled)

        sys.stdout.write(chr(13) + "  %-16s [%s] %3d%% (%4.0fs)   " % (label, bar, pct, time.time() - t0))

        sys.stdout.flush()



    _render()

    ready = False

    import threading, queue

    q = queue.Queue()

    _EOF = object()

    recent = []  # last lines, for debug dump if startup fails



    # Background reader: drains stdout WITHOUT select. The combination of

    # select + readline with buffering left the "listening" line stuck

    # in Python's buffer (select watches the raw fd, not the buffer), so

    # the bar froze at 85% even though the server was already listening.

    def _llama_reader():

        try:

            for _line in proc.stdout:

                q.put(_line)

        finally:

            q.put(_EOF)



    threading.Thread(target=_llama_reader, daemon=True).start()



    HEALTH_TIMEOUT = 900  # 15 min max (USB loading takes 8-15 min)

    while True:

        try:

            line = q.get(timeout=0.4)

        except queue.Empty:

            if not ready and time.time() - t0 > HEALTH_TIMEOUT:

                break

            _render()

            continue

        if line is _EOF:  # server finished before listening

            break

        recent.append(line)

        if len(recent) > 30:

            recent.pop(0)

        low = line.lower()

        if "loading model" in low:

            label, pct = "Loading model", 15

        elif "initializing" in low or "threadpool init" in low:

            label, pct = "Initializing", 60

        elif "model loaded" in low:

            label, pct = "Model loaded", 85

        elif "listening" in low or "main loop" in low:

            ready = True

            break

        _render()



    if ready:

        label, pct = "Ready", 100

    _render()

    print()



    if not ready:

        print("  ⚠ Local model did not start in %.0fs." % (time.time() - t0))

        if recent:

            print("  Last server lines:")

            for _l in recent[-8:]:

                sys.stdout.write("    " + _l.rstrip() + "\n")

        return



    print("  Local model ready (%.0fs)." % (time.time() - t0))

    # (reader thread keeps draining server output in the background)





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

    "You take the blue pill, the story ends, you wake up in your bed and believe whatever you want to believe. You take the red pill, you stay in Wonderland, and I show you how deep the rabbit hole goes.",

    "Whoa. Déjà vu.",

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

    # Terminator (1984 / 1991)

    "I'll be back.",

    "Come with me if you want to live.",

    "Hasta la vista, baby.",

    "I need your clothes, your boots and your motorcycle.",

    "I know now why you cry, but it's something I can never do.",

]





THEME_ANSI = {

    "wargames": "32",  # green

    "amber": "33",     # amber

    "white": "37",     # white

    "cyan": "36",      # cyan

}

def _read_theme():

    """Read theme: from config.yaml (naive parser)."""

    try:

        with open(Path.home() / ".aios" / "config.yaml") as f:

            for line in f:

                if line.strip().startswith("theme:"):

                    return line.split(":", 1)[1].strip()

    except Exception:

        pass

    return "wargames"





_last_quote = None

_quote_pool = []





def _pick_quote():

    """Random quote; shuffles and cycles so each quote appears once before any repeat."""

    global _last_quote, _quote_pool

    import random

    if not _quote_pool:

        _quote_pool = WARGAMES_QUOTES[:]

        random.shuffle(_quote_pool)

        if len(_quote_pool) > 1 and _quote_pool[-1] == _last_quote:

            _quote_pool[-1], _quote_pool[-2] = _quote_pool[-2], _quote_pool[-1]

    q = _quote_pool.pop()

    _last_quote = q

    return q





def _aios_version() -> str:

    """Read the current AIOS version from the CHANGELOG (first "## vX.Y.Z" line).

    Falls back to the legacy banner version if the file is missing."""

    import re as _re

    try:

        changelog = Path(__file__).resolve().parent / "CHANGELOG.md"

        if changelog.exists():

            for line in changelog.read_text(encoding="utf-8", errors="replace").splitlines():

                m = _re.match(r"^##\s+(v[0-9]+\.[0-9]+(?:\.[0-9]+)?)", line.strip())

                if m:

                    return m.group(1)

    except Exception:

        pass

    return "v0.0.0-dev"





def _greet():

    """BBS header + rotating movie quote. No hexagon (boot art is kept elsewhere)."""

    import random

    from agent import _tic, _open_audio, _skip_pressed, _cbreak_on, _cbreak_off

    _open_audio()

    print(f"AIOS/{_aios_version()} — {time.strftime('%a %b %d %Y').upper()}")

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

    """Line input with tic per key (typewriter) and history (arrow keys).

    Sound is controlled by /sound (agent.SOUND_ON)."""

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

            elif ch == "\x1b":  # ESC: arrow sequence

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

        line = "".join(buf)

        if line:

            _input_history.append(line)

        _input_hist_idx = len(_input_history)

        return line

    finally:

        termios.tcsetattr(fd, termios.TCSADRAIN, old)





def _check_internet(timeout=4):

    """True if there is an internet connection (socket to several destinations)."""

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

    """System status in Wargames format."""

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

        lines.append(f"MEM   {avail/1048576:.1f}/{total/1048576:.1f} GB free")

    except Exception:

        pass

    try:

        t, u, f = shutil.disk_usage("/")

        lines.append(f"DISK  {u/1e9:.1f}/{t/1e9:.1f} GB ({f/1e9:.0f} GB free)")

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

        lines.append("NET   " + (" ".join(ips) if ips else "no IP"))

    except Exception:

        pass

    try:

        r = subprocess.run(["journalctl", "-p", "err", "-n", "3", "--no-pager", "-q"],

                           capture_output=True, text=True, timeout=5)

        errs = [l for l in r.stdout.splitlines() if l.strip()]

        lines.append(f"ERR   {len(errs)} recent")

        for e in errs[:3]:

            lines.append("      " + e[:90])

    except Exception:

        pass

    print("\n  === AIOS SYSTEM STATUS ===")

    for l in lines:

        print(f"  {l}")

    print()





def _write_voice_state(config):

    """Persist voice state to data/voice_state.json (i3 bar VOX/MIC icon)."""

    try:

        vc = config.get("voice", {}) if isinstance(config, dict) else {}

        p = Path("data") / "voice_state.json"

        p.parent.mkdir(parents=True, exist_ok=True)

        import json

        p.write_text(json.dumps({"tts": vc.get("tts", "off"), "stt": vc.get("stt", "off")}))

    except Exception:

        pass





def main():

    config = load_or_setup()

    _voice_engine = config.get("voice", {}).get("tts", "off") or "espeak"

    _write_voice_state(config)

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

        provider_env = config.get("cloud", {}).get("provider_env", "")

        api_key = os.environ.get(provider_env, "") if provider_env else os.environ.get("AIOS_API_KEY", os.environ.get(CLOUD_ENV_VARS.get(provider, ""), ""))

        endpoint = config.get("cloud", {}).get("base_url") or CLOUD_ENDPOINTS.get(provider, "https://api.deepseek.com/v1/chat/completions")

        os.environ["AIOS_LLAMA_SERVER"] = endpoint

        os.environ["AIOS_API_KEY"] = api_key

        os.environ["AIOS_CLOUD_MODEL"] = model or "deepseek-chat"

        os.environ["AIOS_CLOUD_CONTEXT"] = str(ctx)

        os.environ["AIOS_CLOUD_AUTH"] = config.get("cloud", {}).get("auth_type", "bearer")
        # Vision (optional): if enabled in config, expose the endpoint + key so
        # describe_screen() works. Users without vision keep browser/OCR.
        vision = config.get("vision", {})
        if vision.get("enabled"):
            os.environ["AIOS_VISION_ENDPOINT"] = vision.get("endpoint", "")
            # Prefer the key from .env (loaded above); fall back to the config
            # for older installs that still have it embedded there.
            os.environ["AIOS_VISION_API_KEY"] = (
                vision.get("api_key") or os.environ.get(provider_env, ""))

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



    # Local model thinking switch (applies to local and hybrid). Must run BEFORE

    # importing agent, because agent.py reads AIOS_LOCAL_THINK when imported.

    if mode in ("local", "hybrid"):

        os.environ["AIOS_LOCAL_THINK"] = "true" if config.get("local", {}).get("think", False) else "false"



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



        if query.lower().startswith("/voice"):



            # Menu like /theme (NOT in the installer: /voice and /theme are chat

            # commands, so they work the same in live and installed).

            vc = config.setdefault("voice", {})

            _arg = query[6:].strip().lower()



            if _arg in ("on", "off"):

                # shortcut: /voice on | /voice off

                if _arg == "on":

                    if vc.get("tts", "off") in (None, "off"):

                        vc["tts"] = _voice_engine

                else:

                    _voice_engine = vc.get("tts") or _voice_engine

                    vc["tts"] = "off"

                    try:

                        import voice

                        voice.stop()

                    except Exception:

                        pass

                try:

                    import yaml

                    CONFIG_FILE.write_text(yaml.dump(config, default_flow_style=False))

                except Exception:

                    pass

                _write_voice_state(config)

                print(f"  Voice output: {'ON' if vc.get('tts') not in (None, 'off') else 'OFF'} ({vc.get('tts')})")

                continue



            tts_opts = {"1": "off", "2": "espeak", "3": "live", "4": "gemini", "5": "openai"}

            stt_opts = {"1": "off", "2": "vosk", "3": "gemini", "4": "openai"}

            langs = ["es", "en", "fr", "de", "it", "pt", "ca"]



            tts_now = vc.get("tts", "off") or "off"

            stt_now = vc.get("stt", "off") or "off"

            lang_now = vc.get("stt_lang") or "es"



            print("  VOICE")

            print(f"    1) Voice output (TTS): {tts_now}")

            print("       off | espeak (local) | live (Gemini, audio nativo) | gemini | openai")

            print(f"    2) Voice input (STT):  {stt_now}")

            print("       off | vosk (local, offline) | gemini | openai")

            print(f"    3) Language:           {lang_now}")

            print("       " + " | ".join(langs))

            print("    (Enter = keep, q = cancel)")



            sel = input("  Option (1-3): ").strip().lower()

            if sel == "q":

                print("  Voice unchanged.")

                continue



            def _ask(prompt, opts):

                while True:

                    v = input(prompt).strip().lower()

                    if not v:

                        return None

                    if v in opts:

                        return opts[v]

                    print("    Invalid. Choose 1-4, or Enter to keep.")



            if sel == "1":

                r = _ask("    TTS (1 off, 2 espeak, 3 live, 4 gemini, 5 openai) [keep]: ",
                     tts_opts)

                if r is not None:

                    vc["tts"] = r

                    if r in (None, "off"):

                        try:

                            import voice

                            voice.stop()

                        except Exception:

                            pass

                    else:

                        _voice_engine = r

            elif sel == "2":

                r = _ask("    STT (1 off, 2 vosk, 3 gemini, 4 openai) [keep]: ", stt_opts)

                if r is not None:

                    vc["stt"] = r

                    if r == "vosk":

                        _l = vc.get("stt_lang") or "es"

                        _mp = f"/usr/local/share/aios/vosk-model-{_l}"

                        if _l == "es" and not os.path.isdir(_mp):

                            _mp = "/usr/local/share/aios/vosk-model"

                        if not os.path.isdir(_mp):

                            print(f"    NOTE: no model for '{_l}' yet (looked in {_mp}).")

                            print("          Speech recognition will do nothing until it is installed.")

            elif sel == "3":

                while True:

                    v = input(f"    Language ({'/'.join(langs)}) [keep]: ").strip().lower()

                    if not v:

                        break

                    if v in langs:

                        vc["stt_lang"] = v

                        _mp = f"/usr/local/share/aios/vosk-model-{v}"

                        if v == "es" and not os.path.isdir(_mp):

                            _mp = "/usr/local/share/aios/vosk-model"

                        mark = "installed" if os.path.isdir(_mp) else "NOT installed"

                        print(f"    Language set to {v} (STT model: {mark})")

                        break

                    print("    Unknown language. " + "/".join(langs))

            else:

                print("  Voice unchanged.")

                continue



            try:

                import yaml

                CONFIG_FILE.write_text(yaml.dump(config, default_flow_style=False))

            except Exception:

                pass

            _write_voice_state(config)



            print(f"  Saved: TTS={vc.get('tts', 'off')} | STT={vc.get('stt', 'off')} | lang={vc.get('stt_lang') or 'es'}")

            print("  (the change applies to the next turn)")

            continue



        if query.lower() == "/mic":

            try:

                import voice

                text = voice.listen(config)

            except Exception:

                text = None

            if text:

                print(f"You: {text}")

                query = text  # fall through to agent.run(query)

            else:

                print("  (No speech detected, or speech-to-text is not configured)")

                continue



        if query.lower().startswith("/sudo"):

            # /sudo is deprecated: run_command now prompts for the sudo password

            # inline (masked) when needed. Keep a no-op so old muscle memory does

            # not crash, and point the user to the new behaviour.

            print("  /sudo is no longer needed — the agent asks for the sudo password")

            print("  automatically (masked) whenever a command needs it.")

            continue



        if query.lower() == "/think":

            if mode not in ("local", "hybrid"):

                print("  Thinking mode is a local-model feature (not available in cloud).")

                continue

            new_state = agent.set_think(not agent.think)

            try:

                import yaml

                cfg = yaml.safe_load(CONFIG_FILE.read_text()) or {}

                cfg.setdefault("local", {})["think"] = new_state

                CONFIG_FILE.write_text(yaml.dump(cfg, default_flow_style=False))

            except Exception:

                pass

            print(f"  Thinking mode: {'ON' if new_state else 'OFF'} (ON = more precise, slower)")

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

            agent.reset()  # keeps the system prompt (identity + rules)

            agent._save_session()

            print("  Session cleared. New conversation.")

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

            while True:

                response = agent.run(query)

                # Barge-in: the user interrupted mid-turn to add info (text or voice).

                # Re-enter the agent loop with the info as a fresh query, keeping the

                # context from before the interruption.

                if isinstance(response, str) and response.startswith("__BARGE__:"):

                    try:

                        _, _bmode, _binfo = response.split(":", 2)

                    except ValueError:

                        _bmode, _binfo = "text", ""

                    if _bmode == "voice":

                        try:

                            import voice

                            _vtext = voice.listen(config)

                        except Exception:

                            _vtext = None

                        if _vtext:

                            print(f"  [Voz: {_vtext}]\n")

                            query = _vtext

                            continue

                        # No speech -> just continue the turn

                        query = "sigue con lo que estabas haciendo"

                        continue

                    if _binfo:

                        print(f"  [Añadido: {_binfo}]\n")

                        query = _binfo

                        continue

                    # Empty text (Tab + Enter) -> just continue the turn

                    query = "sigue con lo que estabas haciendo"

                    continue

                # The response was already printed character by character during the stream.

                # We only add a final newline (explicit CRLF) if the stream did not leave one.

                sys.stdout.write(chr(13) + "\n")

                sys.stdout.flush()

                # run() returns errors and empty responses without streaming

                # (LLM connection error, empty stream, cache). If they are not printed,

                # the prompt returns with no visible reply.

                if response and response.startswith(("LLM connection error",

                                                      "Error reading LLM stream",

                                                      "(empty model response)",

                                                      "(no response)",

                                                      "(continue)",

                                                      "[cache]")):

                    print("  " + response)

                    sys.stdout.flush()

                # Always save session (even on errors) to keep context.

                try:

                    agent._save_session()

                except Exception:

                    pass

                if config.get("voice", {}).get("tts", "off") not in (None, "off"):

                    try:

                        import voice

                        voice.speak(response, config)  # closes/reopens the tic aplay inside its thread

                    except Exception:

                        pass

                break

        except KeyboardInterrupt:

            print("\n[Interrupted]")

            continue





# ─── Error wrapper ────────────────────────────────────────────────────

if __name__ == "__main__":

    try:

        main()

    except EOFError:

        pass  # stdin closed (pipe)

    except Exception as e:

        import sys, traceback

        print(f"\n  ERROR: {e}", file=sys.stderr)

        traceback.print_exc(file=sys.stderr)

        try:

            input("\n  Press Enter to close...")

        except:

            pass

        sys.exit(1)

