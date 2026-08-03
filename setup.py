import readline
readline.parse_and_bind('"\\d": backward-delete-char')
"""AIOS Agent - Configuration setup (first-run wizard)."""
import getpass
import json
import os
import re
import shlex
import subprocess as _sp
import time
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


WPA_DIR = Path("/etc/wpa_supplicant")
SYSTEMD_DIR = Path("/etc/systemd/system")


def _run(cmd, **kwargs):
    """Run a shell command, returning CompletedProcess. cmd may be string or list."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    return _sp.run(cmd, capture_output=True, text=True, **kwargs)


def _run_sudo(cmd, **kwargs):
    """Run a command via sudo if the current effective uid is not 0."""
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    if os.geteuid() != 0:
        cmd = ["sudo"] + cmd
    return _sp.run(cmd, capture_output=True, text=True, **kwargs)


def _which(name):
    """Return the path of an executable or None if not found."""
    for d in os.getenv("PATH", "/usr/bin:/bin:/usr/sbin:/sbin").split(os.pathsep):
        p = Path(d) / name
        if p.is_file():
            return str(p)
    return None


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


def _get_own_ip(iface):
    """Return the IPv4 address of iface, or None."""
    r = _run(["ip", "addr", "show", "dev", iface])
    m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)\b", r.stdout)
    return m.group(1) if m else None


def _iface_has_internet(iface, timeout=5):
    """Verify internet connectivity using curl or ping fallback."""
    curl = _which("curl")
    if curl:
        r = _run([curl, "-m", str(timeout), "-s", "-o", "/dev/null", "-w", "%{http_code}", "https://1.1.1.1"])
        try:
            return int(r.stdout.strip()) == 200
        except ValueError:
            pass
    ping = _which("ping")
    if ping:
        r = _run([ping, "-c", "1", "-W", "3", "1.1.1.1"])
        return r.returncode == 0
    return False


def setup_wifi():
    """WiFi setup wizard: detect interface, scan, connect, persist if possible."""
    clear()
    print_box("WIFI SETUP", ["", "  Detecting wireless interface...", ""])
    time.sleep(0.5)

    iface = None
    r = _run(["iw", "dev"])
    if r.returncode == 0:
        for line in r.stdout.splitlines():
            if "Interface" in line:
                parts = line.split()
                # iw dev output is like: \tInterface wlan0
                for i, p in enumerate(parts):
                    if p == "Interface" and i + 1 < len(parts):
                        candidate = parts[i + 1]
                        # confirm type managed
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
        # Manual network block; escape quotes for ssid and psk.
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

    # Write the file with 600 permissions using sudo tee if needed.
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

    # Stop any existing wpa_supplicant on this interface.
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

    # Request an IP address.
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
        # Persist on installed systems only.
        if SYSTEMD_DIR.exists():
            _run_sudo(["systemctl", "enable", f"wpa_supplicant@{iface}"])
            _run_sudo(["systemctl", "start", f"wpa_supplicant@{iface}"])
            # Try to keep DHCP alive via a simple aios-wifi service if not present.
            svc_path = SYSTEMD_DIR / "aios-wifi.service"
            if not svc_path.exists():
                svc = (
                    "[Unit]\n"
                    "Description=AIOS WiFi connection\n"
                    "After=network.target\n"
                    "\n"
                    "[Service]\n"
                    "Type=forking\n"
                    f"ExecStart=/usr/sbin/wpa_supplicant -B -i {iface} -c {conf_path}\n"
                    f"ExecStartPost=/bin/sh -c 'sleep 3; /sbin/udhcpc -i {iface} -q -n || /sbin/dhcpcd {iface}'\n"
                    "Restart=on-failure\n"
                    "\n"
                    "[Install]\n"
                    "WantedBy=multi-user.target\n"
                )
                _run_sudo(["tee", str(svc_path)], input=svc)
                _run_sudo(["systemctl", "daemon-reload"])
                _run_sudo(["systemctl", "enable", "aios-wifi"])

        clear()
        print_box("WIFI SETUP", ["", f"  WiFi connected to {ssid}", f"  IP: {ip or 'unknown'}", ""])
    else:
        clear()
        reason = "Could not reach the internet" if dhcp_done else "Could not obtain an IP address"
        print_box("WIFI SETUP", ["", f"  Failed to connect to {ssid}", f"  Reason: {reason}", f"  IP: {ip or 'none'}", ""])

    input("  Press Enter to return to menu...")


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
        "  5) WIFI SETUP",
        "     Configure wireless network",
        "",
    ])
    try:
        mode = int(input("  Select (1-5): "))
    except ValueError:
        mode = 0

    if mode == 5:
        setup_wifi()
        return

    if mode not in (1, 2, 3, 4):
        print("\n  Invalid option. Defaulting to LOCAL mode.")

    if mode == 4:
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

    selected = LOCAL_MODELS[0]  # default, may be overridden for local
    if mode not in (1, 2, 3, 4):
        print("\n  Invalid option. Defaulting to LOCAL mode.")
        mode = 1
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
