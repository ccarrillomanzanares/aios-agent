"""AIOS Agent - Boot menu (Wargames style) and first-run setup.

Rewritten 8 Aug 2026 (Carlos): Wargames-style menu, no boxes, computer-
generated "tic" sound (synthesized tone via aplay, no files), greeting only on
first boot, live/install + local/cloud flow, internet check with WiFi proposal
(setup_wifi is kept unchanged - do not change).
"""
import readline
# Reliable backspace: covers ^H and DEL (the two codes sent by terminals)
readline.parse_and_bind('"\\C-h": backward-delete-char')
readline.parse_and_bind('"\\C-?": backward-delete-char')
import getpass
import json
import math
import os
import random
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

_AUDIO = None          # persistent aplay process (generates the "tic")
_TICK_MS = 0.05        # 20 chars/s ~= 3x human typing speed


def _open_audio():
    """Open persistent aplay through stdin (no files: synthesized PCM).
    Minimal buffer/period (512 frames ~= 11.6 ms) so the tic sounds
    immediately. Warm-up: 0.2 s of silence so ALSA opens the device BEFORE the
    first real tic (otherwise the first tics pile up in the pipe and sound late)."""
    global _AUDIO
    try:
        import subprocess as _sp
        _AUDIO = _sp.Popen(
            ["aplay", "-q", "-f", "S16_LE", "-r", "44100", "-c", "1", "-"],
            stdin=_sp.PIPE, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
        )
        # Warm-up: force the device open (0.2 s of silence) before first real tic
        try:
            _AUDIO.stdin.write(b"\x00" * 17640)
            _AUDIO.stdin.flush()
            time.sleep(0.1)
        except Exception:
            pass
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
    """Play a 'tic' per character: 850 Hz, 35 ms (>= ALSA period),
    smooth decay -> sounds individual and continuous, not bunched."""
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


def _skip_pressed():
    """True if the user pressed SPACE during the typewriter (consumes it). Non-blocking."""
    try:
        import select
        if select.select([0], [], [], 0)[0]:
            return os.read(0, 1) == b" "
    except Exception:
        pass
    return False


def _cbreak_on():
    """Enable cbreak mode (each key is available instantly, no echo) if there is a tty.
    Returns (fd, old) to restore with _cbreak_off, or (None, None)."""
    try:
        import termios, tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        tty.setcbreak(fd)
        return fd, old
    except Exception:
        return None, None


def _cbreak_off(fd, old):
    if fd is not None:
        try:
            import termios
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass


def _fix_erase():
    """Set the tty erase character to DEL (0x7f) — canonical prompts
    (getpass, sudo, login) do not erase with backspace if the erase char does
    not match the key (bug '^ and letters', 26 Aug 2026). Also covers the setup
    xterm, which does not read .bashrc or /etc/profile."""
    try:
        import termios
        fd = sys.stdin.fileno()
        attrs = termios.tcgetattr(fd)
        attrs[6][termios.VERASE] = b"\x7f"
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
    except Exception:
        pass


def _read_line():
    """Read a line with correct backspace and protected prompt (fix 25 Aug).

    Uses raw mode + manual keyboard handling: backspace removes from the buffer
    (never the prompt), no stray '^' characters; Ctrl+C interrupts."""
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    buf = []
    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch in ("\r", "\n"):
                break
            if ch in ("\x7f", "\x08"):   # backspace / DEL
                if buf:
                    buf.pop()
                    sys.stdout.write("\b \b")
                    sys.stdout.flush()
                continue
            if ch == "\x1b":             # escape sequence (Delete, arrows)
                import select
                seq = ch
                try:
                    while select.select([fd], [], [], 0.02)[0]:
                        seq += sys.stdin.read(1)
                except Exception:
                    pass
                if seq in ("\x1b[3~", "\x1b[P"):   # Delete (xterm / rxvt)
                    if buf:
                        buf.pop()
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                continue
            if ch == "\x03":              # Ctrl+C
                raise KeyboardInterrupt
            if ch == "\x04":              # Ctrl+D
                break
            if ch.isprintable() or ch in (" ", "\t"):
                buf.append(ch)
                sys.stdout.write(ch)
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    sys.stdout.write("\n")
    sys.stdout.flush()
    return "".join(buf)


def wg(text, delay=_TICK_MS):
    """Print text character by character (Wargames style) + tic per char.
    If the user presses SPACE, write the rest of the text at once."""
    s = str(text)
    fd_cb, old_cb = _cbreak_on()
    try:
        for i, ch in enumerate(s):
            sys.stdout.write(ch)
            sys.stdout.flush()
            if _skip_pressed():
                sys.stdout.write(s[i + 1:])
                sys.stdout.flush()
                break
            _tic()
            time.sleep(delay)
    finally:
        _cbreak_off(fd_cb, old_cb)
    sys.stdout.write("\n")
    sys.stdout.flush()


def wg_input(prompt, delay=_TICK_MS):
    """Prompt with Wargames effect and line input (SPACE = write full prompt)."""
    s = str(prompt)
    fd_cb, old_cb = _cbreak_on()
    try:
        for i, ch in enumerate(s):
            sys.stdout.write(ch)
            sys.stdout.flush()
            if _skip_pressed():
                sys.stdout.write(s[i + 1:])
                sys.stdout.flush()
                break
            _tic()
            time.sleep(delay)
    finally:
        _cbreak_off(fd_cb, old_cb)
    sys.stdout.flush()
    try:
        # Discard pending input (e.g. residual Enter from a subprocess) so
        # the prompt always waits for the user's key (fix 25 Aug).
        try:
            import termios
            termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
        except Exception:
            pass
        return _read_line()
    except EOFError:
        return ""


def _apply_layout(code):
    """Apply the keyboard layout to the console (loadkeys, needs root) and X11 (setxkbmap)."""
    try:
        _run(["sudo", "loadkeys", code])
    except Exception:
        pass
    try:
        # Force console Backspace to DEL (0x7f) for any layout:
        # some keymaps (fr/es) send ^H (0x08) and backspace does not erase
        # in canonical prompts (sudo/getpass) → "^ and letters" characters (26 Aug).
        _run(["sudo", "bash", "-c", "echo 'keycode 14 = Delete' | loadkeys"])
    except Exception:
        pass
    try:
        _sp.run(["setxkbmap", "-layout", code], capture_output=True)
    except Exception:
        pass


_LAYOUTS = {
    "1": ("us", "US / QWERTY"),
    "2": ("fr", "French / AZERTY"),
    "3": ("es", "Spanish / QWERTY-ES"),
    "4": ("de", "German / QWERTZ"),
    "5": ("other", "Other (localectl --list-keymaps)"),
}


def _select_layout():
    """Ask the user for the keyboard layout (TTY + X11). Returns the layout name."""
    wg("Select keyboard layout:")
    for k, (_code, label) in _LAYOUTS.items():
        wg(f"  {k}) {label}")
    choice = wg_input("> ").strip()
    if choice not in _LAYOUTS:
        wg("  Using default (US / QWERTY).")
        _apply_layout("us")
        return "us"
    code = _LAYOUTS[choice][0]
    if code == "other":
        code = wg_input("Layout name (e.g. be, cz, it): ").strip() or "us"
    _apply_layout(code)
    return code


# ---------------------------------------------------------------------------
# Utilities (inherited from previous setup - they work, do not touch)
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

# Pages where to get each provider's API key (for firefox)
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

_KB_LAYOUT = "us"   # keyboard layout chosen on first boot (persisted in config.yaml)

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

# Color themes (aios-xterm reads the config and applies the colors)
THEMES = {
    "wargames": ("#00ff66", "Wargames - neon green (default)"),
    "amber": ("#ffb000", "Amber - old terminal phosphor"),
    "white": ("#ffffff", "White - classic"),
    "cyan": ("#00cccc", "Cyan - modern"),
}

# Iconic WarGames (1983) quotes - rotating greeting
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

_last_quote = None
_quote_pool = []


def _pick_quote():
    """Random quote; shuffles and cycles so each quote appears once before any repeat."""
    global _last_quote, _quote_pool
    if not _quote_pool:
        _quote_pool = WARGAMES_QUOTES[:]
        random.shuffle(_quote_pool)
        if len(_quote_pool) > 1 and _quote_pool[-1] == _last_quote:
            _quote_pool[-1], _quote_pool[-2] = _quote_pool[-2], _quote_pool[-1]
    q = _quote_pool.pop()
    _last_quote = q
    return q


def _select_theme():
    """Ask the user for a color theme (Wargames style). Returns the theme name."""
    names = list(THEMES)
    wg("")
    wg("Select the color theme:")
    for i, n in enumerate(names, 1):
        wg(f"  {i}) {THEMES[n][1]}")
    wg("")
    while True:
        raw = wg_input("> ").strip()
        try:
            opt = int(raw) if raw else 1
        except ValueError:
            opt = -1
        if 1 <= opt <= len(names):
            return names[opt - 1]
        wg(f"Invalid option. Choose 1-{len(names)}.")


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


def _check_local_requirements():
    """Compare machine resources with the minimum for Qwen3-8B local.
    Returns a line with the verdict (could work / better not try it)."""
    try:
        cores = os.cpu_count() or 4
        ram = detect_ram_gb()
        req_cores, req_ram = 4, 8
        if cores >= req_cores and ram >= req_ram:
            return (f"     This machine could run it ({cores} cores, {ram} GB RAM) "
                    f"- slow, about typing speed.")
        return (f"     I have reviewed this machine's resources: {cores} cores, {ram} GB RAM. "
                f"They are below the minimum required ({req_cores}+ cores, {req_ram} GB). "
                f"Better not to use local mode.")
    except Exception:
        return ""


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
    """Connectivity check: TCP to direct IPs + domains, and DNS UDP as a
    last resort (networks that filter outgoing TCP). No false negatives from
    filtered destinations: one working destination is enough."""
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
    # Last resort: DNS UDP (sometimes outgoing TCP is filtered but UDP is not)
    for server in ("1.1.1.1", "8.8.8.8", "208.67.222.222"):
        try:
            import struct
            import random
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            tid = random.randint(0, 65535)
            q = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0) + \
                b"\x07example\x03com\x00\x00\x01\x00\x01"
            s.sendto(q, (server, 53))
            s.recvfrom(512)
            s.close()
            return True
        except Exception:
            continue
    return False


def _wait_internet(attempts=5, delay=3):
    """Retry internet check with delay (DHCP may take time after associating)."""
    for _ in range(attempts):
        if _iface_has_internet():
            return True
        time.sleep(delay)
    return False


def _net_summary():
    """Return visible (ip, gateway) — for diagnosing 'no internet'.
    Uses absolute ip paths (Debian/Ubuntu places it in /usr/sbin, outside PATH)."""
    ip, gw = "", ""
    ip_bin = next((p for p in ("/usr/sbin/ip", "/usr/bin/ip", "/sbin/ip") if os.path.exists(p)), None)
    if ip_bin is None:
        return ip, gw
    try:
        out = subprocess.run([ip_bin, "-o", "addr", "show"], capture_output=True,
                             text=True, timeout=5).stdout
        for line in out.splitlines():
            if " inet " in line and "127.0.0.1" not in line:
                ip = line.split()[3].split("/")[0]
                break
    except Exception:
        pass
    try:
        out = subprocess.run([ip_bin, "route"], capture_output=True,
                             text=True, timeout=5).stdout
        for line in out.splitlines():
            if line.startswith("default"):
                gw = line.split()[2]
                break
    except Exception:
        pass
    return ip, gw


def _ensure_dns():
    """Ensure nameservers in /etc/resolv.conf (udhcpc does not write them:
    without DNS, the check and all networking fail even if there is an IP)."""
    try:
        p = Path("/etc/resolv.conf")
        txt = p.read_text() if p.exists() else ""
        if "nameserver" not in txt:
            with open(p, "a") as f:
                f.write("nameserver 208.67.222.222\nnameserver 208.67.220.220\n")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# WiFi wizard (inherited from previous setup - WORKS, DO NOT CHANGE)
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
        _ensure_dns()  # udhcpc does not write resolv.conf: without DNS the network looks dead
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
# Cloud flow (inherited from previous setup - reused without boxes)
# ---------------------------------------------------------------------------

def validate_api_key(provider, api_key, base_url=None, auth_type="bearer"):
    """Test the API key with a lightweight request (hard timeout, DNS-safe)."""
    base_url = base_url or CLOUD_ENDPOINTS.get(provider, "")
    if not base_url:
        return True
    # Custom endpoints (Other) come with the full chat completions URL:
    # derive the /models URL from it for validation.
    if "chat/completions" in base_url:
        base_url = base_url.rsplit("/chat/completions", 1)[0]

    if auth_type == "x-api-key":
        headers = {"X-API-Key": api_key, "User-Agent": "AIOS-Setup/1.0"}
    else:
        headers = {"Authorization": f"Bearer {api_key}", "User-Agent": "AIOS-Setup/1.0"}
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
            ("deepseek-v4-flash", "deepseek-v4-flash - fast and cheap"),
            ("deepseek-v4-pro", "deepseek-v4-pro - deep reasoning"),
        ],
        "env": "DEEPSEEK_API_KEY",
        "context_limit": 1048576,
    },
    {
        "name": "OpenAI",
        "models": [
            ("gpt-4o", "gpt-4o - maximum quality"),
            ("gpt-4o-mini", "gpt-4o-mini - economical"),
        ],
        "env": "OPENAI_API_KEY",
        "context_limit": 128000,
    },
    {
        "name": "Anthropic",
        "models": [
            ("claude-sonnet-4", "claude-sonnet-4 - balanced"),
            ("claude-haiku-3.5", "claude-haiku-3.5 - fast"),
        ],
        "env": "ANTHROPIC_API_KEY",
        "context_limit": 200000,
    },
    {
        "name": "Google Gemini",
        "models": [
            ("gemini-2.0-flash", "gemini-2.0-flash - fast"),
            ("gemini-2.0-pro", "gemini-2.0-pro - quality"),
        ],
        "env": "GOOGLE_API_KEY",
        "context_limit": 1048576,
    },
    {
        "name": "Kimi / Moonshot",
        "models": [
            ("kimi-k2.7-code", "kimi-k2.7-code - code"),
            ("kimi-k2.7-thinking", "kimi-k2.7-thinking - reasoning"),
        ],
        "env": "KIMI_API_KEY",
        "context_limit": 128000,
    },
    {
        "name": "Ollama Cloud",
        "models": [
            ("kimi-k2.7-code", "kimi-k2.7-code - code and execution"),
            ("kimi-k2.7-thinking", "kimi-k2.7-thinking - reasoning"),
        ],
        "env": "OLLAMA_CLOUD_API_KEY",
        "context_limit": 128000,
    },
    {
        "name": "Ollama Hardened",
        "models": [
            ("hf.co/gabriellarson/Moonlight-16B-A3B-Instruct-GGUF:Q3_K_M", "Moonlight-16B-A3B Q3_K_M - 16B MoE (3B active)"),
        ],
        "env": "OLLAMA_HARDENED_API_KEY",
        "context_limit": 8192,
        "base_url": "https://webuillama.ccmai.org:8443/v1/chat/completions",
        "auth_type": "x-api-key",
    },
    {
        "name": "OpenRouter",
        "models": [],
        "env": "OPENROUTER_API_KEY",
        "context_limit": 128000,
    },
]


def select_provider_and_model():
    """Provider selection (no boxes). Returns (provider, model) or (None, None)."""
    while True:
        wg("")
        wg("Select the cloud provider:")
        for i, p in enumerate(PROVIDERS, 1):
            wg(f"  {i}) {p['name']}")
        wg("  9) Other (custom endpoint)")
        wg("  10) Back")
        wg("")
        try:
            opt = int(wg_input("  Select (1-10): "))
        except ValueError:
            wg("Invalid option. Choose 1-10.")
            continue

        if opt == 10:
            return None, None
        if opt == 9:
            wg("")
            wg("Custom provider (Other):")
            name = wg_input("  Provider name: ").strip()
            if not name:
                wg("Provider name cannot be empty.")
                continue
            url = wg_input("  Chat completions endpoint URL\n  (e.g. https://api.example.com/v1/chat/completions): ").strip()
            if not url:
                wg("Endpoint URL cannot be empty.")
                continue
            model = wg_input("  Model name: ").strip()
            if not model:
                wg("Model name cannot be empty.")
                continue
            wg("  Auth type:")
            wg("    b) Bearer  (Authorization: Bearer ***  — most providers)")
            wg("    x) X-API-Key  (header X-API-Key: ***  — Ollama hardened)")
            auth_opt = wg_input("  Select (b/x): ").strip().lower()
            auth_type = "x-api-key" if auth_opt == "x" else "bearer"
            prov = {"name": name, "models": [(model, model)], "env": "OTHER_API_KEY",
                    "context_limit": 128000, "base_url": url, "auth_type": auth_type}
            return prov, model
        if opt < 1 or opt > 8:
            wg("Invalid option. Choose 1-10.")
            continue

        prov = PROVIDERS[opt - 1]

        if prov["name"] == "OpenRouter":
            wg("")
            wg("Enter the model name:")
            wg("e.g. deepseek/deepseek-v4-flash, openai/gpt-4o")
            model = wg_input("  Model: ").strip()
            if not model:
                return None, None
            return prov, model

        while True:
            wg("")
            for i, m in enumerate(prov["models"]):
                wg(f"  {chr(97 + i)}) {m[1]}")
            wg("  q) Back")
            wg("")
            opt2 = wg_input("  Select (a-b, q): ").strip().lower()

            if opt2 == "q":
                return None, None
            if len(opt2) != 1:
                wg("Invalid option.")
                continue

            idx = ord(opt2) - 97
            if idx < 0 or idx >= len(prov["models"]):
                wg(f"Invalid option. Choose a-{chr(96 + len(prov['models']))}, or q.")
                continue

            return prov, prov["models"][idx][0]


def _legacy_box(title, lines):
    """Simple presentation WITHOUT BOXES (Wargames style) for the wifi wizard.
    The setup_wifi mechanism is not touched: only the drawing changes."""
    wg("")
    wg(title)
    for l in lines:
        wg(l if l else " ")


# ---------------------------------------------------------------------------
# Voice (TTS/STT) — local and cloud
# ---------------------------------------------------------------------------

VOICE_ENV = {
    "gemini": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
}


def _upsert_env(key_name, value):
    """Add/update a KEY=value line in ~/.aios/.env (keeps the rest)."""
    env_path = CONFIG_DIR / ".env"
    lines = []
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                if not line.startswith(f"{key_name}="):
                    lines.append(line)
    lines.append(f"{key_name}={value}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)


def _voice_flow():
    """Pick voice output (TTS) and input (STT); ask for the API key of cloud
    engines (Gemini/OpenAI) and save it to .env, separate from the chat key.
    Returns {"tts": ..., "stt": ..., "tts_lang": "auto"}."""
    wg("")
    wg("VOICE (optional) - the agent can talk and listen")
    wg("")
    wg("Voice output (text-to-speech):")
    wg("  1) Off")
    wg("  2) Local robotic voice (espeak-ng)     [offline]")
    wg("  3) Cloud natural voice (Google Gemini) [API key]")
    wg("  4) Cloud natural voice (OpenAI)        [API key]")
    tts_map = {"1": "off", "2": "espeak", "3": "gemini", "4": "openai"}
    while True:
        t = wg_input("  Select (1-4) [2]: ").strip() or "2"
        if t in tts_map:
            break
        wg("  Invalid option. Choose 1-4.")
    tts = tts_map[t]

    wg("")
    wg("Voice input (speech-to-text):")
    wg("  1) Off   2) Local (vosk)   3) Gemini   4) OpenAI")
    stt_map = {"1": "off", "2": "vosk", "3": "gemini", "4": "openai"}
    while True:
        s = wg_input("  Select (1-4) [2]: ").strip() or "2"
        if s in stt_map:
            break
        wg("  Invalid option. Choose 1-4.")
    stt = stt_map[s]

    # One key per cloud provider (shared between TTS and STT).
    for eng in sorted({tts, stt}):
        if eng not in VOICE_ENV:
            continue
        env_name = VOICE_ENV[eng]
        prov_name = "Google Gemini" if eng == "gemini" else "OpenAI"
        url = CLOUD_KEY_URLS.get(prov_name, "")
        wg("")
        wg(f"{prov_name} API key is required for voice ({eng}).")
        if url:
            wg(f"  Get one at: {url}")
        key = wg_input(f"  {prov_name} API key (Enter to turn off {eng} voice): ").strip()
        if not key:
            if tts == eng:
                tts = "off"
            if stt == eng:
                stt = "off"
            continue
        wg("  Testing key...")
        base_url = CLOUD_ENDPOINTS.get(prov_name, "")
        valid = validate_api_key(prov_name, key, base_url)
        if valid is True:
            wg(f"  {prov_name} key valid. Saved.")
        else:
            wg("  Could not verify the key (no internet or wrong key). Saving anyway.")
        _upsert_env(env_name, key)

    return {"tts": tts, "stt": stt, "tts_lang": "auto"}


# ---------------------------------------------------------------------------
# Flows
# ---------------------------------------------------------------------------

def _write_local_config(theme="wargames", voice=None):
    """Write config.yaml in local mode and start the llama service."""
    import yaml
    model_path = Path("/usr/local/share/aios/models") / LOCAL_MODELS[0]["file"]
    if not model_path.exists():
        wg(f"Model {LOCAL_MODELS[0]['file']} not found.")
        wg("Use the LLM ISO or place it at /usr/local/share/aios/models/")
        return False

    ram_gb = detect_ram_gb()
    ctx = auto_context(ram_gb)
    # Local thinking mode: OFF by default (fast). ON reasons before answering.
    think_opt = wg_input("Enable thinking mode? (slower, more precise) [y/N]: ").strip().lower()
    think = think_opt in ("y", "yes")
    config = {
        "mode": "local",
        "theme": theme,
        "keyboard": _KB_LAYOUT,
        "local": {
            "model": LOCAL_MODELS[0]["file"],
            "model_name": LOCAL_MODELS[0]["name"],
            "threads": detect_cpu(),
            "context": ctx,
            "think": think,
        },
        "cloud": {"provider": None, "model": None},
        "voice": voice or {"tts": "off", "stt": "off", "tts_lang": "auto"},
    }
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    _sp.run(["systemctl", "enable", "aios-llama.service"], capture_output=True)
    _sp.run(["systemctl", "start", "aios-llama.service"], capture_output=True)
    return True


def _write_cloud_config(prov_data, model, key, theme="wargames", voice=None):
    """Write cloud config + API key in .env."""
    import yaml
    config = {
        "mode": "cloud",
        "theme": theme,
        "keyboard": _KB_LAYOUT,
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
            "base_url": prov_data.get("base_url"),
            "auth_type": prov_data.get("auth_type", "bearer"),
            "provider_env": prov_data.get("env", ""),
        },
        "voice": voice or {"tts": "off", "stt": "off", "tts_lang": "auto"},
    }
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)

    _upsert_env(prov_data["env"], key)
    return True


def _cloud_flow(theme="wargames", voice=None):
    """Cloud flow: firefox with the provider + provider + API key + validation."""
    prov_data, model = select_provider_and_model()
    if not (prov_data and model):
        return False

    # Do not open Firefox by default: the user may already have the key at hand.
    # Print the URL and ask if they want us to open it.
    fx = _which("firefox")
    url = CLOUD_KEY_URLS.get(prov_data["name"])
    if url:
        wg(f"Get your {prov_data['name']} API key at: {url}")
    else:
        wg(f"Get your {prov_data['name']} API key from the provider console.")
    if fx and url:
        open_fx = wg_input("  Open Firefox to get the API key? (y/N): ").strip().lower()
        if open_fx in ("y", "yes"):
            _sp.Popen([fx, url], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
            wg(f"  Opening {prov_data['name']} in Firefox...")

    while True:
        wg("")
        key = wg_input("  API Key: ").strip()
        if not key:
            wg("No API key provided. Cancelling cloud setup.")
            return False
        wg("Testing API key...")
        valid = validate_api_key(prov_data["name"], key, prov_data.get("base_url"), prov_data.get("auth_type", "bearer"))
        if valid is True:
            wg("API key is valid.")
            return _write_cloud_config(prov_data, model, key, theme, voice)
        elif valid is False:
            wg("Invalid API key. Check and try again.")
            continue
        else:
            retry = wg_input("(Could not verify API key. Use anyway? (Y/n): ").strip().lower()
            if retry != "n":
                return _write_cloud_config(prov_data, model, key, theme, voice)
            continue


def _live_flow(online):
    """Live mode: propose local or cloud."""
    wg("")
    wg("AIOS live mode.")
    wg("How do you want to use the agent?")
    wg("  1) LOCAL - the built-in Qwen3-8B model (no internet needed)")
    wg("     Requires: CPU at least like an Intel i5-1035G1 (4 cores / 8 threads,")
    wg("     1.0 GHz base / 3.6 GHz boost, 6 MB cache), 8 GB RAM.")
    wg("     Note: runs slow, about human typing speed.")
    wg(_check_local_requirements())
    wg("  2) CLOUD - an external model via API")
    wg("")
    while True:
        m = wg_input("> ")
        if m in ("1", "2"):
            break
        wg("Invalid option. Please choose 1 or 2.")

    if m == "2" and not online:
        wg("Cloud mode requires internet (none detected).")
        opt = wg_input("Use LOCAL mode instead? (Y/n): ").strip().lower()
        if opt in ("", "y", "yes"):
            wg("Switching to LOCAL.")
            m = "1"
        else:
            return  # back to menu

    # Final mode: theme and voice are chosen ONCE.
    theme = _select_theme()
    voice = _voice_flow()

    if m == "2":
        if _cloud_flow(theme, voice):
            _sp.run(["aios-theme", theme], capture_output=True)
            wg("Setup complete. Starting the AIOS agent...")
            return True
        wg("Cloud setup cancelled. Falling back to LOCAL.")

    wg("")
    wg("LOCAL mode - Qwen3-8B (Q4_K_M)")
    if _write_local_config(theme, voice):
        _sp.run(["aios-theme", theme], capture_output=True)
        wg("Setup complete. Starting the AIOS agent...")
        return True
    return False


def _install_flow(online):
    """Install mode: local or cloud, then aios-install --mode."""
    wg("")
    wg("Installing AIOS to the hard disk.")
    wg("How do you want to use the agent on the installed system?")
    wg("  1) LOCAL - the built-in Qwen3-8B model")
    wg("     Requires: CPU at least like an Intel i5-1035G1 (4 cores / 8 threads,")
    wg("     1.0 GHz base / 3.6 GHz boost, 6 MB cache), 8 GB RAM.")
    wg("     Note: runs slow, about human typing speed.")
    wg(_check_local_requirements())
    wg("  2) CLOUD - an external model via API")
    wg("")
    while True:
        m = wg_input("> ")
        if m in ("1", "2"):
            break
        wg("Invalid option. Please choose 1 or 2.")

    mode = "local"
    theme = "wargames"
    if m == "2" and not online:
        wg("Cloud mode requires internet (none detected).")
        opt = wg_input("Use LOCAL mode instead? (Y/n): ").strip().lower()
        if opt in ("", "y", "yes"):
            wg("Switching to LOCAL.")
            m = "1"
        else:
            return  # back to menu

    # Final mode: theme and voice ONCE.
    theme = _select_theme()
    voice = _voice_flow()

    if m == "2" and online:
        if _cloud_flow(theme, voice):
            mode = "cloud"
        else:
            wg("Cloud setup cancelled. Falling back to LOCAL.")

    # Local thinking mode: OFF by default. Only asked in local mode.
    think = False
    if mode == "local":
        think_opt = wg_input("Enable thinking mode? (slower, more precise) [y/N]: ").strip().lower()
        think = think_opt in ("y", "yes")

    wg("")
    ntp_opt = wg_input("Set the correct time automatically using an internet time server? (y/N): ").strip().lower()
    if ntp_opt == "y":
        setup_ntp(standalone=False)
    wg("")
    wg("Launching the installer...")
    ret = _sp.run(["sudo", "aios-install", "--mode", mode, "--theme", theme, "--layout", _KB_LAYOUT,
                   "--think", "1" if think else "0",
                   "--tts", voice["tts"], "--stt", voice["stt"]])
    if ret.returncode == 2:
        wg("Installation cancelled.")
        wg_input("Press Enter to return to the menu...")
        return
    if ret.returncode != 0:
        wg("Installation aborted or failed.")
        wg_input("Press Enter to return to the menu...")
        return

    wg("Installation complete. Remove the installation media and reboot.")
    again = wg_input("Reboot now? (y/N): ").strip().lower()
    if again == "y":
        _sp.run(["sudo", "reboot"])


def setup_ntp(standalone=True):
    """Configure automatic time via external NTP server (systemd-timesyncd).
    standalone=False: called from the install flow (no final Enter prompt)."""
    print_box = _legacy_box  # keep original visual, it works (fix 25 Aug: NameError)
    print_box("NTP SETUP", ["", "  Automatic time sync via external NTP server.", ""])
    server = input("  NTP server [pool.ntp.org]: ").strip() or "pool.ntp.org"
    _run(["sudo", "tee", "/etc/systemd/timesyncd.conf"],
         input=f"[Time]\nNTP={server}\n")
    _run(["sudo", "systemctl", "enable", "systemd-timesyncd"])
    _run(["sudo", "systemctl", "restart", "systemd-timesyncd"])
    _run(["sudo", "timedatectl", "set-ntp", "true"])
    time.sleep(2)
    r = _run(["timedatectl", "status"])
    if r.stdout:
        for line in r.stdout.splitlines()[:6]:
            wg(line.strip())
    wg("")
    if standalone:
        input("  Press Enter to return to the menu...")


def main():
    if CONFIG_FILE.exists():
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _fix_erase()
    _open_audio()
    clear()

    # Greeting (first boot) - movie quote + welcome + help (25 Aug)
    wg(_pick_quote())
    time.sleep(0.4)
    wg("You have just booted Artificial Intelligence Operating System.")
    wg("Press F1 or Super+F1 (Super = the Windows key) to view the keyboard shortcuts")
    wg("")

    # Keyboard layout (first boot) — applies TTY + X11 and is persisted
    global _KB_LAYOUT
    _KB_LAYOUT = _select_layout()
    wg("")

    # Main menu (loop: after live or install it returns to menu; only "0" exits)
    while True:
        wg("What would you like to do?")
        wg("")
        wg("  1) Test AIOS in live mode, without installing")
        wg("  2) Install AIOS to the hard disk")
        wg("  0) Exit to shell")
        wg("")
        wg("Note: AIOS has only been tested on machines without multi-boot setups.")
        wg("DISCLAIMER: installation will ERASE ALL DATA on the disk.")
        wg("There is no warranty of any kind, expressed or implied.")
        wg("")
        choice = wg_input("> ")
        if choice == "0":
            break
        elif choice not in ("1", "2"):
            wg("Invalid option. Please choose 0, 1 or 2.")
            continue

        # Internet check
        wg("")
        wg("Checking internet connection...")
        online = _iface_has_internet()
        if not online:
            wg("No internet connection detected.")
            opt = wg_input("Configure WiFi now? (y/N): ").strip().lower()
            if opt == "y":
                setup_wifi()
                wg("")
                wg("Waiting for the network to come up...")
                online = _wait_internet()
                if not online:
                    ip, gw = _net_summary()
                    wg("Still no internet connection.")
                    wg(f"  (IP: {ip or 'none'} · Gateway: {gw or 'none'} — no external host is reachable)")
                    wg("CLOUD mode will not be available — it will fall back to LOCAL.")
            else:
                wg("Continuing without internet.")

        if choice == "2":
            _install_flow(online)
        else:
            if _live_flow(online):
                break  # setup completed → exit setup.py (autolaunch starts the agent)


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
