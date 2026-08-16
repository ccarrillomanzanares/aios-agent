"""AIOS Agent - Boot menu (Wargames style) and first-run setup.

Reescrito 8 Ago 2026 (Carlos): menu estilo Wargames, sin cajas, sonido
"tic" generado por el propio ordenador (tono sintetizado via aplay, sin
archivos), saludo solo al primer arranque, flujo live/install + local/cloud,
check de internet con propuesta de WiFi (setup_wifi intacta - no cambiar).
"""
import getpass
import json
import math
import os
import re
import shlex
import struct
import subprocess as _sp
import sys
import threading
import time
import urllib.request as url_req
from pathlib import Path

# ---------------------------------------------------------------------------
# Wargames effect
# ---------------------------------------------------------------------------

_AUDIO = None          # proceso aplay persistente (genera el "tic")
_TICK_MS = 0.05        # 20 chars/s ~= 3x velocidad de tecleo humano


def _open_audio():
    """Abrir aplay persistente por stdin (sin archivos: PCM sintetizado).
    Buffer/period minimos (1024 frames ~= 23 ms) para que el tic suene
    inmediatamente, por caracter (el buffer por defecto acumulaba ~1 s)."""
    global _AUDIO
    try:
        _AUDIO = _sp.Popen(
            ["aplay", "-q", "-f", "S16_LE", "-r", "44100", "-c", "1",
             "--buffer-size=512", "--period-size=512", "-"],
            stdin=_sp.PIPE, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
        )
    except Exception:
        _AUDIO = None


def _close_audio():
    global _AUDIO
    if _AUDIO is not None:
        try:
            _AUDIO.stdin.close()
        except Exception:
            pass
        _AUDIO = None


def _tic():
    """Reproducir un 'tic' por caracter: 850 Hz, 35 ms (>= periodo ALSA),
    decaimiento suave -> suena individual y continuo, sin agruparse."""
    if _AUDIO is None or _AUDIO.poll() is not None:
        return
    sr, dur, freq = 44100, 0.035, 850.0
    n = int(sr * dur)
    pcm = bytearray()
    for i in range(n):
        t = i / sr
        env = math.exp(-t / 0.012)
        pcm += struct.pack("<h", int(12000 * env * math.sin(2 * math.pi * freq * t)))
    try:
        _AUDIO.stdin.write(bytes(pcm))
        _AUDIO.stdin.flush()
    except Exception:
        pass


def wg(text, delay=_TICK_MS):
    """Imprimir texto caracter a caracter (estilo Wargames) + tic por char."""
    for ch in str(text):
        sys.stdout.write(ch)
        sys.stdout.flush()
        _tic()
        time.sleep(delay)
    sys.stdout.write("\n")
    sys.stdout.flush()


def wg_input(prompt, delay=_TICK_MS):
    """Prompt con efecto Wargames y lectura de una linea."""
    for ch in str(prompt):
        sys.stdout.write(ch)
        sys.stdout.flush()
        _tic()
        time.sleep(delay)
    sys.stdout.flush()
    try:
        return input("")
    except EOFError:
        return ""


# ---------------------------------------------------------------------------
# Utilidades (heredadas del setup anterior - funcionan, no tocar)
# ---------------------------------------------------------------------------

CLOUD_ENDPOINTS = {
    "DeepSeek": "https://api.deepseek.com/v1",
    "OpenAI": "https://api.openai.com/v1",
    "Anthropic": "https://api.anthropic.com/v1",
    "Google Gemini": "https://generativelanguage.googleapis.com/v1beta",
    "Kimi / Moonshot": "https://api.moonshot.cn/v1",
    "Ollama Cloud": "https://api.ollama.cloud/v1",
    "OpenRouter": "https://openrouter.ai/api/v1",
}

# Paginas donde obtener la API key de cada proveedor (para firefox)
CLOUD_KEY_URLS = {
    "DeepSeek": "https://platform.deepseek.com/api_keys",
    "OpenAI": "https://platform.openai.com/api-keys",
    "Anthropic": "https://console.anthropic.com/settings/keys",
    "Google Gemini": "https://aistudio.google.com/apikey",
    "Kimi / Moonshot": "https://platform.moonshot.cn/console/api-keys",
    "Ollama Cloud": "https://cloud.ollama.com",
    "OpenRouter": "https://openrouter.ai/keys",
}

CONFIG_DIR = Path.home() / ".aios"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

WPA_DIR = Path("/etc/wpa_supplicant")
SYSTEMD_DIR = Path("/etc/systemd/system")

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


def _run(cmd, **kwargs):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    return _sp.run(cmd, capture_output=True, text=True, **kwargs)


def _run_sudo(cmd, **kwargs):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    if os.geteuid() != 0:
        cmd = ["sudo"] + cmd
    return _sp.run(cmd, capture_output=True, text=True, **kwargs)


def _which(name):
    for d in os.getenv("PATH", "/usr/bin:/bin:/usr/sbin:/sbin").split(os.pathsep):
        p = Path(d) / name
        if p.is_file():
            return str(p)
    return None


def detect_cpu():
    cores = os.cpu_count() or 4
    return max(1, int(cores * 0.875))


def detect_ram_gb():
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    kb = int(line.split()[1])
                    return round(kb / 1024 / 1024)
    except Exception:
        pass
    return 12


def auto_context(ram_gb):
    if ram_gb <= 8:
        return 8192
    elif ram_gb <= 16:
        return 32768
    else:
        return 65536


def clear():
    os.system("clear" if os.name == "posix" else "cls")


def _get_own_ip(iface):
    r = _run(["ip", "addr", "show", "dev", iface])
    m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)\b", r.stdout)
    return m.group(1) if m else None


def _iface_has_internet(iface=None, timeout=4):
    """Check de conectividad: IPs directas (sin DNS) + dominios reales (con DNS).
    Un destino filtrado por la red (p.ej. 1.1.1.1:443) no da falso negativo."""
    import socket
    targets = [
        ("1.1.1.1", 443), ("1.0.0.1", 443), ("8.8.8.8", 53),
        ("google.com", 443), ("google.es", 443), ("archlinux.org", 443),
    ]
    for host, port in targets:
        try:
            s = socket.create_connection((host, port), timeout=timeout)
            s.close()
            return True
        except Exception:
            continue
    return False


def _ensure_dns():
    """Asegurar nameservers en /etc/resolv.conf (udhcpc no los escribe:
    sin DNS, el check y toda la red fallan aunque haya IP)."""
    try:
        p = Path("/etc/resolv.conf")
        txt = p.read_text() if p.exists() else ""
        if "nameserver" not in txt:
            with open(p, "a") as f:
                f.write("nameserver 208.67.222.222\nnameserver 208.67.220.220\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# WiFi wizard (heredado del setup anterior - FUNCIONA, NO CAMBIAR)
# ---------------------------------------------------------------------------

def setup_wifi():
    """WiFi setup wizard: detect interface, scan, connect, persist if possible."""
    clear()
    print_box = _legacy_box  # keep original visual, it works
    print_box("WIFI SETUP", ["", "  Detecting wireless interface...", ""])
    time.sleep(0.5)

    iface = None
    r = _run(["iw", "dev"])
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if "Interface" in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == "Interface" and i + 1 < len(parts):
                        candidate = parts[i + 1]
                        mode_r = _run(["iw", "dev", candidate, "info"])
                        if candidate not in (iface or "") and "managed" in mode_r.stdout.lower():
                            iface = candidate
                            break
            if iface:
                break

    if not iface:
        net_dir = Path("/sys/class/net")
        if net_dir.exists():
            for dev in sorted(net_dir.iterdir()):
                if dev.name.startswith("wl"):
                    iface = dev.name
                    break

    if not iface:
        clear()
        print_box("WIFI SETUP", ["", "  No wireless interface found.", "  Make sure a WiFi adapter is available.", ""])
        input("  Press Enter to return to menu...")
        return

    clear()
    print_box("WIFI SETUP", ["", f"  Interface detected: {iface}", "  Bringing interface up...", ""])
    _run_sudo(["ip", "link", "set", iface, "up"])
    time.sleep(1)

    ssids = []
    scan_lines = []
    for attempt in range(2):
        r = _run_sudo(["iw", "dev", iface, "scan"], timeout=10)
        if r.returncode == 0:
            scan_lines = r.stdout.splitlines()
            break
        if "busy" in r.stderr.lower() or r.returncode != 0:
            time.sleep(2)

    seen = set()
    for line in scan_lines:
        if "SSID:" in line:
            parts = line.split("SSID:", 1)
            if len(parts) == 2:
                ssid = parts[1].strip()
                if ssid and ssid not in seen:
                    ssids.append(ssid)
                    seen.add(ssid)

    clear()
    if ssids:
        lines = ["", f"  Wireless networks found ({len(ssids)}):", ""]
        for i, s in enumerate(ssids, 1):
            lines.append(f"  {i}) {s}")
        lines.extend(["", "  0) Enter SSID manually", "", f"  Selected interface: {iface}", ""])
        print_box("WIFI SETUP", lines)
        try:
            opt = int(input("  Select (0-{}): ".format(len(ssids))))
        except ValueError:
            opt = 0
        if 1 <= opt <= len(ssids):
            ssid = ssids[opt - 1]
        else:
            ssid = input("  SSID: ").strip()
    else:
        print_box("WIFI SETUP", ["", "  Could not scan networks.", "  You can still enter the SSID manually.", "", f"  Interface: {iface}", ""])
        ssid = input("  SSID: ").strip()

    if not ssid:
        clear()
        print_box("WIFI SETUP", ["", "  No SSID provided. Returning to menu.", ""])
        input("  Press Enter to return to menu...")
        return

    clear()
    print_box("WIFI SETUP", ["", f"  SSID: {ssid}", "  Enter the WiFi password.", ""])
    password = getpass.getpass("  Password: ").strip()

    WPA_DIR.mkdir(parents=True, exist_ok=True)
    conf_path = WPA_DIR / f"wpa_supplicant-{iface}.conf"

    wpa_pass = _which("wpa_passphrase")
    conf_content = None
    if wpa_pass and password:
        r = _run([wpa_pass, ssid, password])
        if r.returncode == 0 and "network={" in r.stdout:
            conf_content = r.stdout
    if not conf_content:
        safe_ssid = ssid.replace('"', '\\"')
        if password:
            safe_psk = password.replace('"', '\\"')
            psk_line = f"\tpsk=\"{safe_psk}\"\n"
        else:
            psk_line = "\tkey_mgmt=NONE\n"
        conf_content = (
            "ctrl_interface=/run/wpa_supplicant\n"
            "update_config=1\n"
            "\n"
            "network={\n"
            f"\tssid=\"{safe_ssid}\"\n"
            f"{psk_line}"
            "}\n"
        )

    try:
        if os.geteuid() == 0:
            with open(conf_path, "w") as f:
                f.write(conf_content)
            os.chmod(conf_path, 0o600)
        else:
            r = _run(["sudo", "tee", str(conf_path)], input=conf_content)
            if r.returncode == 0:
                _run(["sudo", "chmod", "600", str(conf_path)])
            else:
                raise OSError(r.stderr or "tee failed")
    except Exception as e:
        clear()
        print_box("WIFI SETUP", ["", f"  Failed to write {conf_path}: {e}", ""])
        input("  Press Enter to return to menu...")
        return

    clear()
    print_box("WIFI SETUP", ["", f"  Configuration saved to {conf_path}", "  Connecting...", ""])

    _run_sudo(["pkill", "-f", "wpa_supplicant"])
    time.sleep(0.5)

    wpa_supp = _which("wpa_supplicant")
    if not wpa_supp:
        clear()
        print_box("WIFI SETUP", ["", "  wpa_supplicant not found. Cannot connect.", ""])
        input("  Press Enter to return to menu...")
        return

    r = _run_sudo([wpa_supp, "-B", "-i", iface, "-c", str(conf_path)])
    if r.returncode != 0:
        clear()
        print_box("WIFI SETUP", ["", "  Failed to start wpa_supplicant:", f"  {r.stderr.strip()}", ""])
        input("  Press Enter to return to menu...")
        return
    time.sleep(3)

    dhcp_done = False
    udhcpc = _which("udhcpc")
    if udhcpc:
        r = _run_sudo([udhcpc, "-i", iface, "-q", "-n"], timeout=15)
        dhcp_done = r.returncode == 0
    if not dhcp_done:
        dhcpcd = _which("dhcpcd")
        if dhcpcd:
            r = _run_sudo([dhcpcd, iface], timeout=15)
            dhcp_done = r.returncode == 0

    ip = _get_own_ip(iface)
    connected = _iface_has_internet(iface)

    if connected:
        _ensure_dns()  # udhcpc no escribe resolv.conf: sin DNS la red parece muerta
        if SYSTEMD_DIR.exists():
            _run_sudo(["systemctl", "enable", f"wpa_supplicant@{iface}"])
            _run_sudo(["systemctl", "start", f"wpa_supplicant@{iface}"])
            net_path = Path("/etc/systemd/network/20-wifi-dhcp.network")
            if not net_path.exists():
                net_cfg = (
                    "[Match]\n"
                    "Name=wl*\n"
                    "\n"
                    "[Network]\n"
                    "DHCP=ipv4\n"
                    "DNS=208.67.222.222 208.67.220.220\n"
                    "\n"
                    "[DHCP]\n"
                    "UseDNS=no\n"
                )
                _run_sudo(["tee", str(net_path)], input=net_cfg)
                _run_sudo(["systemctl", "restart", "systemd-networkd"])

        clear()
        print_box("WIFI SETUP", ["", f"  WiFi connected to {ssid}", f"  IP: {ip or 'unknown'}", ""])
    else:
        clear()
        reason = "Could not reach the internet" if dhcp_done else "Could not obtain an IP address"
        print_box("WIFI SETUP", ["", f"  Failed to connect to {ssid}", f"  Reason: {reason}", f"  IP: {ip or 'none'}", ""])

    input("  Press Enter to return to menu...")


# ---------------------------------------------------------------------------
# Cloud flow (heredado del setup anterior - reutilizado sin cajas)
# ---------------------------------------------------------------------------

def validate_api_key(provider, api_key):
    """Test the API key with a lightweight request (hard timeout, DNS-safe)."""
    base_url = CLOUD_ENDPOINTS.get(provider, "")
    if not base_url:
        return True

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
    t.join(timeout=12)
    return result.get("value")


PROVIDERS = [
    {
        "name": "DeepSeek",
        "models": [
            ("deepseek-v4-flash", "deepseek-v4-flash - rapido y barato"),
            ("deepseek-v4-pro", "deepseek-v4-pro - razonamiento profundo"),
        ],
        "env": "DEEPSEEK_API_KEY",
        "context_limit": 1048576,
    },
    {
        "name": "OpenAI",
        "models": [
            ("gpt-4o", "gpt-4o - calidad maxima"),
            ("gpt-4o-mini", "gpt-4o-mini - economico"),
        ],
        "env": "OPENAI_API_KEY",
        "context_limit": 128000,
    },
    {
        "name": "Anthropic",
        "models": [
            ("claude-sonnet-4", "claude-sonnet-4 - equilibrio"),
            ("claude-haiku-3.5", "claude-haiku-3.5 - rapido"),
        ],
        "env": "ANTHROPIC_API_KEY",
        "context_limit": 200000,
    },
    {
        "name": "Google Gemini",
        "models": [
            ("gemini-2.0-flash", "gemini-2.0-flash - rapido"),
            ("gemini-2.0-pro", "gemini-2.0-pro - calidad"),
        ],
        "env": "GOOGLE_API_KEY",
        "context_limit": 1048576,
    },
    {
        "name": "Kimi / Moonshot",
        "models": [
            ("kimi-k2.7-code", "kimi-k2.7-code - codigo"),
            ("kimi-k2.7-thinking", "kimi-k2.7-thinking - razonamiento"),
        ],
        "env": "KIMI_API_KEY",
        "context_limit": 128000,
    },
    {
        "name": "Ollama Cloud",
        "models": [
            ("kimi-k2.7-code", "kimi-k2.7-code - codigo y ejecucion"),
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


def select_provider_and_model():
    """Provider selection (sin cajas). Returns (provider, model) or (None, None)."""
    while True:
        wg("")
        wg("Select the cloud provider:")
        for i, p in enumerate(PROVIDERS, 1):
            wg(f"  {i}) {p['name']}")
        wg("  8) Back")
        wg("")
        try:
            opt = int(wg_input("  Select (1-8): "))
        except ValueError:
            return None, None

        if opt == 8:
            return None, None
        if opt < 1 or opt > 7:
            return None, None

        prov = PROVIDERS[opt - 1]

        if prov["name"] == "OpenRouter":
            wg("")
            wg("Enter the model name:")
            wg("e.g. deepseek/deepseek-v4-flash, openai/gpt-4o")
            model = wg_input("  Model: ").strip()
            if not model:
                return None, None
            return prov, model

        wg("")
        for i, m in enumerate(prov["models"]):
            wg(f"  {chr(97 + i)}) {m[1]}")
        wg("  q) Back")
        wg("")
        opt2 = wg_input("  Select (a-b, q): ").strip().lower()

        if opt2 == "q":
            return None, None

        idx = ord(opt2) - 97
        if idx < 0 or idx >= len(prov["models"]):
            return None, None

        return prov, prov["models"][idx][0]


def _legacy_box(title, lines):
    """Presentacion simple SIN CAJAS (estilo Wargames) para el wizard wifi.
    El mecanismo de setup_wifi no se toca: solo cambia el dibujo."""
    wg("")
    wg(title)
    for l in lines:
        wg(l if l else " ")


# ---------------------------------------------------------------------------
# Flujos
# ---------------------------------------------------------------------------

def _write_local_config():
    """Escribir config.yaml en modo local y arrancar el servicio llama."""
    import yaml
    model_path = Path("/usr/local/share/aios/models") / LOCAL_MODELS[0]["file"]
    if not model_path.exists():
        wg(f"Model {LOCAL_MODELS[0]['file']} not found.")
        wg("Use the LLM ISO or place it at /usr/local/share/aios/models/")
        return False

    ram_gb = detect_ram_gb()
    ctx = auto_context(ram_gb)
    config = {
        "mode": "local",
        "local": {
            "model": LOCAL_MODELS[0]["file"],
            "model_name": LOCAL_MODELS[0]["name"],
            "threads": detect_cpu(),
            "context": ctx,
        },
        "cloud": {"provider": None, "model": None},
    }
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    _sp.run(["systemctl", "enable", "aios-llama.service"], capture_output=True)
    _sp.run(["systemctl", "start", "aios-llama.service"], capture_output=True)
    return True


def _write_cloud_config(prov_data, model, key):
    """Escribir config cloud + API key en .env."""
    import yaml
    config = {
        "mode": "cloud",
        "local": {
            "model": LOCAL_MODELS[0]["file"],
            "model_name": LOCAL_MODELS[0]["name"],
            "threads": detect_cpu(),
            "context": auto_context(detect_ram_gb()),
        },
        "cloud": {
            "provider": prov_data["name"],
            "model": model,
            "context_limit": prov_data.get("context_limit", 128000),
        },
    }
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    env_path = CONFIG_DIR / ".env"
    env_lines = []
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if not line.startswith(f"{prov_data['env']}="):
                    env_lines.append(line)
    env_lines.append(f"{prov_data['env']}={key}\n")
    with open(env_path, "w") as f:
        f.writelines(env_lines)
    return True


def _cloud_flow():
    """Flujo cloud: firefox con el proveedor + provider + API key + validacion."""
    prov_data, model = select_provider_and_model()
    if not (prov_data and model):
        return False

    # Firefox para obtener/copiar la API key del proveedor
    fx = _which("firefox")
    url = CLOUD_KEY_URLS.get(prov_data["name"])
    if fx:
        _sp.Popen([fx, url] if url else [fx], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
        wg(f"Opening {prov_data['name']} in Firefox to get your API key...")
    else:
        wg("Firefox not found - get your API key from the provider console.")

    while True:
        wg("")
        key = wg_input("  API Key: ").strip()
        if not key:
            wg("No API key provided. Cancelling cloud setup.")
            return False
        wg("Testing API key...")
        valid = validate_api_key(prov_data["name"], key)
        if valid is True:
            wg("API key is valid.")
            return _write_cloud_config(prov_data, model, key)
        elif valid is False:
            wg("Invalid API key. Check and try again.")
            continue
        else:
            retry = wg_input("(Could not verify API key. Use anyway? (Y/n): ").strip().lower()
            if retry != "n":
                return _write_cloud_config(prov_data, model, key)
            continue


def _live_flow(online):
    """Modo live: proponer local o cloud."""
    wg("")
    wg("AIOS live mode.")
    wg("How do you want to use the agent?")
    wg("  1) LOCAL - the built-in Qwen3-8B model (no internet needed)")
    wg("  2) CLOUD - an external model via API")
    wg("")
    m = wg_input("> ")

    if m == "2":
        if not online:
            wg("Cloud mode requires internet. Falling back to LOCAL.")
            m = "1"
        else:
            if _cloud_flow():
                wg("Setup complete. Starting the AIOS agent...")
                return
            wg("Cloud setup cancelled. Falling back to LOCAL.")
            m = "1"

    wg("")
    wg("LOCAL mode - Qwen3-8B (Q4_K_M)")
    if _write_local_config():
        wg("Setup complete. Starting the AIOS agent...")


def _install_flow(online):
    """Modo instalar: local o cloud, luego aios-install --mode."""
    wg("")
    wg("Installing AIOS to the hard disk.")
    wg("How do you want to use the agent on the installed system?")
    wg("  1) LOCAL - the built-in Qwen3-8B model")
    wg("  2) CLOUD - an external model via API")
    wg("")
    m = wg_input("> ")

    mode = "local"
    if m == "2":
        if not online:
            wg("Cloud mode requires internet. Falling back to LOCAL.")
        else:
            if _cloud_flow():
                mode = "cloud"
            else:
                wg("Cloud setup cancelled. Falling back to LOCAL.")

    wg("")
    wg("Launching the installer...")
    ret = _sp.run(["sudo", "aios-install", "--mode", mode])
    if ret.returncode != 0:
        wg("Installation aborted or failed.")
        wg_input("Press Enter to return to the menu...")
        return

    wg("Installation complete. WiFi settings have been copied to the disk.")
    again = wg_input("Reboot now? (y/N): ").strip().lower()
    if again == "y":
        _sp.run(["sudo", "reboot"])


def main():
    if CONFIG_FILE.exists():
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _open_audio()
    clear()

    # Saludo (primer arranque)
    wg("Greetings, Professor Falken")
    time.sleep(0.4)
    clear()

    # Menu principal
    wg("You have just booted Artificial Intelligence Operating System.")
    wg("What would you like to do?")
    wg("")
    wg("  1) Test AIOS in live mode, without installing")
    wg("  2) Install AIOS to the hard disk")
    wg("")
    wg("Note: AIOS has only been tested on machines without multi-boot setups.")
    wg("DISCLAIMER: installation will ERASE ALL DATA on the disk.")
    wg("There is no warranty of any kind, expressed or implied.")
    wg("")
    choice = wg_input("> ")

    if choice not in ("1", "2"):
        wg("Invalid option. Continuing with live mode.")
        choice = "1"

    # Check de internet
    wg("")
    wg("Checking internet connection...")
    online = _iface_has_internet()
    if not online:
        wg("No internet connection detected.")
        opt = wg_input("Configure WiFi now? (y/N): ").strip().lower()
        if opt == "y":
            setup_wifi()
            wg("")
            wg("Checking internet connection again...")
            online = _iface_has_internet()
            if not online:
                wg("Still no internet. Continuing anyway.")
        else:
            wg("Continuing without internet.")

    if choice == "2":
        _install_flow(online)
    else:
        _live_flow(online)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Exiting.")
    except Exception as e:
        print(f"\n  Error: {e}")
    finally:
        _close_audio()
    os._exit(0)
