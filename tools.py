"""Tools for the SRE agent — native function calling."""
import json
import os
import sys
import re
import signal
import subprocess
import time
import shlex
from pathlib import Path

import requests
import yaml
from playbook import run_playbook
from process import process_start, process_send, process_close, process_list


# sudo password cache (session only): run_command passes it to sudo -S.
# The user sets it with /sudo <password> in chat; never persisted to disk.
_SUDO_PASSWORD = None


def set_sudo_password(pw):
    """Store the sudo password for this session (passed to sudo -S)."""
    global _SUDO_PASSWORD
    _SUDO_PASSWORD = pw


def has_sudo_password():
    return bool(_SUDO_PASSWORD)


def _is_blocked_command(command: str) -> bool:
    """Return True if command matches an unconditionally blocked dangerous pattern."""
    lower = command.lower()
    if re.search(r'\brm\s+-rf\s+/\s*$', lower) or re.search(r'\brm\s+-rf\s+/*\b', lower):
        return True
    if re.search(r'\bdd\s+if=\S+\s+of=/dev/\S+', lower):
        return True
    if re.search(r'\bmkfs\.\w+\s+\S+', lower):
        return True
    if re.search(r'\bfdisk\b', lower):
        return True
    if re.search(r'\bchmod\b.*(?:-r\s+)?000\b', lower):
        return True
    return False


def _is_destructive_command(command: str) -> bool:
    """Return True if command requires human confirmation before execution."""
    lower = command.lower()
    if re.search(r'\brm\s+-rf\b', lower):
        return True
    if re.search(r'\bsudo\s+rm\b', lower):
        return True
    if re.search(r'\b>\s*/dev/sd[a-z]', lower):
        return True
    if re.search(r'\bFORMAT_BLOCKED\b', lower):
        return True
    if re.search(r'\bdd\s+if=\S+', lower):
        return True
    return False


def _confirm_destructive(command: str, timeout: int = 10) -> bool:
    """Ask user for confirmation before running a destructive command."""
    import sys as _sys
    _sys.stderr.write(f"\u26a0\ufe0f Destructive command detected: {command}. Continue? (y/N): ")
    _sys.stderr.flush()
    try:
        def _timeout_handler(signum, frame):
            raise TimeoutError
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)
        try:
            answer = _sys.stdin.readline().strip()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        return answer in ("y", "Y")
    except TimeoutError:
        _sys.stderr.write("Confirmation timeout\n")
        return False
    except Exception:
        return False


def run_command(command: str, timeout: int = 30, retry: bool = True) -> str:
    """Execute a shell command. Returns JSON with stdout, stderr, exit_code, elapsed."""
    # sven install/upgrade/sync takes minutes (DB sync + download + install): generous timeout.
    if any(kw in command for kw in ("sven install", "sven upgrade", "sven sync", "sven update")):
        timeout = 600
    if _is_blocked_command(command):
        return json.dumps({"error": "Command blocked: dangerous operation", "exit_code": -1,
                          "stdout": "", "stderr": "Blocked for security reasons"}, ensure_ascii=False)

    if _is_destructive_command(command):
        if not _confirm_destructive(command):
            return json.dumps({"error": "Command cancelled by user", "exit_code": -1,
                              "stdout": "", "stderr": "Cancelled by user"}, ensure_ascii=False)

    t0 = time.time()
    attempts = 0
    max_attempts = 3
    current_command = command

    # sudo: on disk it asks for a password. Pass it to "sudo -S" through stdin.
    # If no password is cached, return a clear error (the agent must ask the
    # user to run /sudo <password>).
    uses_sudo = bool(re.search(r"\bsudo\b", current_command))
    if uses_sudo and not _SUDO_PASSWORD:
        return json.dumps({"stdout": "", "stderr": "sudo requires a password — set it first with /sudo <password>",
                           "exit_code": -1, "elapsed": 0.0}, ensure_ascii=False)
    if uses_sudo:
        current_command = re.sub(r"\bsudo\b", "sudo -S", current_command, count=1)

    # stdin: sven asks ":: Proceed? [Y/n]" → auto-confirm; sudo -S reads the password.
    _auto_confirm = any(kw in command for kw in ("sven install", "sven upgrade", "sven update"))
    stdin_parts = []
    if uses_sudo:
        stdin_parts.append(_SUDO_PASSWORD + "\n")
    if _auto_confirm:
        stdin_parts.append("y\ny\ny\ny\n")
    stdin_arg = None if stdin_parts else subprocess.DEVNULL
    stdin_input = "".join(stdin_parts) if stdin_parts else None

    while attempts < max_attempts:
        attempts += 1
        elapsed = time.time() - t0
        remaining = max(0.1, timeout - elapsed)
        try:
            r = subprocess.run(current_command, shell=True, capture_output=True, text=True,
                               timeout=remaining, stdin=stdin_arg, input=stdin_input)
            stdout = r.stdout.strip()[:5000]
            stderr = r.stderr.strip()[:2000]

            if retry and r.returncode != 0 and ("apt" in current_command or "apt-get" in current_command):
                lower_err = (stdout + "\n" + stderr).lower()
                if "lock" in lower_err or "unable to lock" in lower_err:
                    if attempts < max_attempts:
                        if "could not get lock" in lower_err and not current_command.startswith("sudo apt-get"):
                            if current_command.startswith("apt "):
                                current_command = "sudo apt-get" + current_command[3:]
                            elif current_command.startswith("sudo apt "):
                                current_command = "sudo apt-get" + current_command[8:]
                        else:
                            time.sleep(3)
                        continue

            return json.dumps({"stdout": stdout, "stderr": stderr, "exit_code": r.returncode,
                              "elapsed": round(time.time() - t0, 2)}, ensure_ascii=False)
        except subprocess.TimeoutExpired:
            return json.dumps({"stdout": "", "stderr": f"Timeout ({timeout}s)", "exit_code": 124,
                              "elapsed": timeout}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"stdout": "", "stderr": str(e), "exit_code": -1, "elapsed": round(time.time() - t0, 2)}, ensure_ascii=False)

    return json.dumps({"stdout": "", "stderr": "Retries exhausted", "exit_code": -1,
                      "elapsed": round(time.time() - t0, 2)}, ensure_ascii=False)


def read_file(path: str) -> str:
    """Read a file. Returns JSON with content or error."""
    try:
        p = Path(path).resolve()
        if not p.exists():
            return json.dumps({"error": f"Does not exist: {path}"}, ensure_ascii=False)
        content = p.read_text(encoding="utf-8", errors="replace")
        return json.dumps({"path": str(p), "content": content[:3000], "size": len(content)}, ensure_ascii=False)
    except PermissionError:
        return json.dumps({"error": f"Permission denied: {path}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def write_file(path: str, content: str) -> str:
    """Write a file. Warns if the path is a system directory."""
    try:
        p = Path(path).resolve()
        danger_zones = ["/etc/", "/boot/", "/sys/", "/proc/", "/dev/"]
        for zone in danger_zones:
            if str(p).startswith(zone):
                return json.dumps({"warning": f"System path ({zone}). Write blocked.", "path": str(p)}, ensure_ascii=False)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return json.dumps({"ok": True, "path": str(p), "size": len(content)}, ensure_ascii=False)
    except PermissionError:
        return json.dumps({"error": f"Permission denied: {path}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def web_search(query: str, limit: int = 3) -> str:
    """Search the web via local Firecrawl (port 3002). Returns JSON with results."""
    url = "http://localhost:3002/v1/search"
    payload = {"query": query, "limit": limit}
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        results = []
        if isinstance(data, list):
            for item in data[:limit]:
                if isinstance(item, dict):
                    results.append({"title": item.get("title", item.get("name", "")),
                                    "url": item.get("url", item.get("link", "")),
                                    "description": item.get("description", item.get("snippet", item.get("content", "")))})
        elif isinstance(data, dict):
            candidates = data.get("data", data.get("results", []))
            for item in candidates[:limit]:
                if isinstance(item, dict):
                    results.append({"title": item.get("title", item.get("name", "")),
                                    "url": item.get("url", item.get("link", "")),
                                    "description": item.get("description", item.get("snippet", item.get("content", "")))})
        return json.dumps({"query": query, "count": len(results), "results": results}, ensure_ascii=False)
    except requests.exceptions.ConnectionError as e:
        return json.dumps({"error": "Could not connect to Firecrawl", "details": str(e)}, ensure_ascii=False)
    except requests.exceptions.Timeout:
        return json.dumps({"error": "Timeout contacting Firecrawl (30s)"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error in web_search: {e}"}, ensure_ascii=False)


def git_operation(op: str, args: str = "") -> str:
    """Run allowed git operations in /home/ccmai/sre-agent/. Returns JSON."""
    repo = "/home/ccmai/sre-agent"
    op = op.strip().lower()
    allowed = {"status", "commit", "push", "diff", "log"}
    rejected = {"reset", "rebase", "merge", "stash"}
    if op in rejected:
        return json.dumps({"error": f"Git operation '{op}' not allowed"}, ensure_ascii=False)
    if op not in allowed:
        return json.dumps({"error": f"Unknown operation: {op}. Allowed: {', '.join(sorted(allowed))}"}, ensure_ascii=False)
    lowered = args.lower()
    if "branch" in lowered and ("-d" in lowered or "-delete" in lowered or "-D" in args):
        return json.dumps({"error": "Deleting branches is not allowed"}, ensure_ascii=False)
    command = f"git -C {repo} {op} {args}" if args else f"git -C {repo} {op}"
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        if op == "commit" and (not args or "-m" not in args):
            return json.dumps({"error": "commit requires a message (-m)"}, ensure_ascii=False)
        return json.dumps({"stdout": r.stdout.strip()[:2000], "stderr": r.stderr.strip()[:2000], "exit_code": r.returncode}, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"stdout": "", "stderr": "Timeout (30s)", "exit_code": 124}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"stdout": "", "stderr": str(e), "exit_code": -1}, ensure_ascii=False)


def mcp_call(server: str, tool: str, args: str = "{}") -> str:
    """Call a tool on an MCP server via HTTP. Returns JSON."""
    try:
        parsed_args = json.loads(args) if args else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"args is not valid JSON: {e}"}, ensure_ascii=False)
    base = server if server.startswith("http://") or server.startswith("https://") else f"http://{server}"
    base = base.rstrip("/")
    endpoints = [f"{base}/v1/tools/{tool}", f"{base}/tools/{tool}", f"{base}/mcp/{tool}", f"{base}/{tool}"]
    last_error = ""
    for endpoint in endpoints:
        try:
            r = requests.post(endpoint, json=parsed_args, timeout=15)
            if r.status_code in (404, 405):
                last_error = f"{endpoint} -> {r.status_code}"
                continue
            r.raise_for_status()
            return json.dumps({"server": server, "tool": tool, "result": r.json() if r.text else {}}, ensure_ascii=False)
        except requests.exceptions.ConnectionError as e:
            last_error = f"Could not connect to {server}: {e}"
            break
        except requests.exceptions.Timeout:
            last_error = f"Timeout connecting to {server}"
            break
        except Exception as e:
            last_error = f"{endpoint} -> {e}"
            continue
    return json.dumps({"error": f"MCP server did not respond or tool '{tool}' does not exist", "details": last_error}, ensure_ascii=False)


# ──────────────────────────────────────────────────────────────────────────────
# Vision / GUI interaction tools
# ──────────────────────────────────────────────────────────────────────────────

SCREENSHOT_PATH = "/tmp/aios-shot.png"


def _display_env():
    """Return a copy of the current environment with DISPLAY=:0."""
    env = os.environ.copy()
    env["DISPLAY"] = ":0"
    return env


def screenshot() -> str:
    """Capture the screen to /tmp/aios-shot.png. Returns JSON with path and size."""
    env = _display_env()
    try:
        # Primary: scrot
        r = subprocess.run(
            ["scrot", SCREENSHOT_PATH],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0 and os.path.exists(SCREENSHOT_PATH):
            return json.dumps(
                {
                    "path": SCREENSHOT_PATH,
                    "size": os.path.getsize(SCREENSHOT_PATH),
                    "method": "scrot",
                },
                ensure_ascii=False,
            )

        # Fallback: xwd + ImageMagick convert
        fallback = "xwd -root -display :0 | convert xwd:- " + shlex.quote(SCREENSHOT_PATH)
        r2 = subprocess.run(
            fallback,
            env=env,
            shell=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
        if r2.returncode == 0 and os.path.exists(SCREENSHOT_PATH):
            return json.dumps(
                {
                    "path": SCREENSHOT_PATH,
                    "size": os.path.getsize(SCREENSHOT_PATH),
                    "method": "xwd+convert",
                },
                ensure_ascii=False,
            )

        stderr = (r.stderr or "") + " | fallback: " + (r2.stderr or "")
        return json.dumps(
            {"error": "Screenshot failed", "stderr": stderr.strip()[:1000]},
            ensure_ascii=False,
        )
    except subprocess.TimeoutExpired as e:
        return json.dumps(
            {"error": f"Screenshot timeout ({e.timeout}s)"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": f"Screenshot error: {e}"}, ensure_ascii=False)


def ocr(path: str = "") -> str:
    """Extract text from an image using tesseract. Returns JSON with text.

    If no path is provided, captures a screenshot first.
    """
    image_path = path.strip() if path else SCREENSHOT_PATH

    if not image_path or image_path == SCREENSHOT_PATH:
        if not os.path.exists(SCREENSHOT_PATH):
            res = screenshot()
            try:
                parsed = json.loads(res)
                if "error" in parsed:
                    return res
            except Exception:
                pass
        image_path = SCREENSHOT_PATH

    if not os.path.exists(image_path):
        return json.dumps(
            {"error": f"Image not found: {image_path}"},
            ensure_ascii=False,
        )

    env = _display_env()
    try:
        r = subprocess.run(
            ["tesseract", image_path, "stdout", "-l", "eng"],
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        text = r.stdout.strip()[:2000]
        if r.returncode != 0:
            stderr = r.stderr.strip()[:1000]
            return json.dumps(
                {"error": "OCR failed", "stderr": stderr, "text": text},
                ensure_ascii=False,
            )
        return json.dumps(
            {"path": image_path, "text": text, "length": len(r.stdout.strip())},
            ensure_ascii=False,
        )
    except subprocess.TimeoutExpired as e:
        return json.dumps(
            {"error": f"OCR timeout ({e.timeout}s)"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": f"OCR error: {e}"}, ensure_ascii=False)


def xdotool_type(text: str) -> str:
    """Type text into the focused X11 window. Returns JSON with ok/error."""
    if text is None or text == "":
        return json.dumps({"error": "text is required"}, ensure_ascii=False)
    env = _display_env()
    try:
        r = subprocess.run(
            ["xdotool", "type", "--delay", "10", "--", text],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            return json.dumps(
                {"error": "xdotool type failed", "stderr": r.stderr.strip()[:1000]},
                ensure_ascii=False,
            )
        return json.dumps(
            {"ok": True, "typed_chars": len(text)},
            ensure_ascii=False,
        )
    except subprocess.TimeoutExpired as e:
        return json.dumps(
            {"error": f"xdotool type timeout ({e.timeout}s)"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": f"xdotool type error: {e}"}, ensure_ascii=False)


def xdotool_key(key: str) -> str:
    """Press a key or key combination via xdotool. Returns JSON with ok/error."""
    if key is None or key == "":
        return json.dumps({"error": "key is required"}, ensure_ascii=False)
    env = _display_env()
    try:
        r = subprocess.run(
            ["xdotool", "key", "--", key],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            return json.dumps(
                {"error": "xdotool key failed", "stderr": r.stderr.strip()[:1000]},
                ensure_ascii=False,
            )
        return json.dumps({"ok": True, "key": key}, ensure_ascii=False)
    except subprocess.TimeoutExpired as e:
        return json.dumps(
            {"error": f"xdotool key timeout ({e.timeout}s)"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": f"xdotool key error: {e}"}, ensure_ascii=False)


def xdotool_click(x: int, y: int) -> str:
    """Move the mouse to (x, y) and click the left button. Returns JSON with ok/error."""
    try:
        x = int(x)
        y = int(y)
    except (TypeError, ValueError):
        return json.dumps({"error": "x and y must be integers"}, ensure_ascii=False)
    env = _display_env()
    try:
        r = subprocess.run(
            ["xdotool", "mousemove", str(x), str(y), "click", "1"],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode != 0:
            return json.dumps(
                {"error": "xdotool click failed", "stderr": r.stderr.strip()[:1000]},
                ensure_ascii=False,
            )
        return json.dumps({"ok": True, "x": x, "y": y}, ensure_ascii=False)
    except subprocess.TimeoutExpired as e:
        return json.dumps(
            {"error": f"xdotool click timeout ({e.timeout}s)"},
            ensure_ascii=False,
        )
    except Exception as e:
        return json.dumps({"error": f"xdotool click error: {e}"}, ensure_ascii=False)


# Schemas for function calling
def list_desktop_apps() -> str:
    """List installed graphical/desktop applications (parses .desktop files)."""
    import glob
    apps = []
    seen = set()
    for pattern in ("/usr/share/applications/*.desktop", "/usr/local/share/applications/*.desktop"):
        for f in sorted(glob.glob(pattern)):
            name = exec_ = comment = ""
            nodisplay = False
            try:
                with open(f, encoding="utf-8", errors="replace") as fh:
                    section = False
                    for line in fh:
                        line = line.rstrip("\n")
                        if line == "[Desktop Entry]":
                            section = True
                            continue
                        if line.startswith("[") and line != "[Desktop Entry]":
                            break
                        if not section:
                            continue
                        if line.startswith("Name="):
                            name = line[5:].strip()
                        elif line.startswith("Exec="):
                            exec_ = line[5:].strip()
                        elif line.startswith("Comment="):
                            comment = line[8:].strip()
                        elif line.startswith("NoDisplay=true"):
                            nodisplay = True
                            break
            except Exception:
                continue
            if name and not nodisplay and name not in seen:
                seen.add(name)
                apps.append({"name": name, "exec": exec_, "comment": comment})
    return json.dumps({"count": len(apps), "apps": apps}, ensure_ascii=False)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command on Linux.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command"},
                    "timeout": {"type": "integer", "description": "Timeout (default 30)"},
                    "retry": {"type": "boolean", "description": "Retry on apt errors (default true)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_desktop_apps",
            "description": "List installed graphical/desktop applications (parses .desktop files). Use to answer 'what GUI apps are installed' or 'is X installed'.",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file. Use for logs, configs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write to a file. System paths blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path"},
                    "content": {"type": "string", "description": "Content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for technical documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results (default 3)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_operation",
            "description": "Run git operations (status, commit, push, diff, log).",
            "parameters": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "description": "status, commit, push, diff, log"},
                    "args": {"type": "string", "description": "Additional arguments"}
                },
                "required": ["op"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_call",
            "description": "Call a tool on an MCP server via HTTP.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server": {"type": "string"},
                    "tool": {"type": "string"},
                    "args": {"type": "string", "description": "JSON arguments (default {})"}
                },
                "required": ["server", "tool"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_playbook",
            "description": "Execute a YAML playbook with sequential steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to .yml playbook"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_start",
            "description": "Start a long-running interactive process.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string"},
                    "timeout": {"type": "integer", "description": "Timeout (default 30)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_send",
            "description": "Send text to a running process.",
            "parameters": {
                "type": "object",
                "properties": {
                    "proc_id": {"type": "string"},
                    "text": {"type": "string"},
                    "timeout": {"type": "integer"}
                },
                "required": ["proc_id", "text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_close",
            "description": "Terminate a running interactive process.",
            "parameters": {
                "type": "object",
                "properties": {
                    "proc_id": {"type": "string"}
                },
                "required": ["proc_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "process_list",
            "description": "List all running interactive processes.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cloud_reasoning",
            "description": "Delegate a complex reasoning task to a cloud LLM (DeepSeek/GPT/Claude). Use for architecture design, debugging, multi-step planning. Receives the full conversation context.",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "The reasoning task for the cloud model"}
                },
                "required": ["prompt"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_context_usage",
            "description": "Shows current context usage: tokens used vs maximum. Helps monitor session size.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Capture the current X11 screen and save it to /tmp/aios-shot.png. Returns the file path and size.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ocr",
            "description": "Extract text from an image using Tesseract. If no path is given, takes a screenshot first.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional absolute path to an image. Defaults to the last screenshot."}
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xdotool_type",
            "description": "Type text into the currently focused X11 window using xdotool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"}
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xdotool_key",
            "description": "Press a key or key combination via xdotool in the active X11 window.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key or combination, e.g. Return, ctrl+c, alt+Tab"}
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "xdotool_click",
            "description": "Move the mouse to the given screen coordinates and click the left mouse button.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"}
                },
                "required": ["x", "y"]
            }
        }
    },
]


def cloud_reasoning(args: dict, context=None) -> str:
    """Send a reasoning task to a cloud LLM with full conversation context."""
    import os as _os

    endpoint = _os.environ.get("AIOS_CLOUD_ENDPOINT", "https://api.deepseek.com/v1/chat/completions")
    api_key = _os.environ.get("AIOS_API_KEY", "")
    model = _os.environ.get("AIOS_CLOUD_MODEL", "deepseek-v4-pro")

    if not api_key:
        return json.dumps({"error": "No API key configured for cloud reasoning"}, ensure_ascii=False)

    prompt = args.get("prompt", "")
    if not prompt:
        return json.dumps({"error": "No prompt provided"}, ensure_ascii=False)

    # Build minimal messages: context summary + prompt
    messages = []
    if context and len(context) > 2:
        summary = "\n".join(
            f"{m['role']}: {m['content'][:200]}"
            for m in context[-10:]  # last 10 messages for context
        )
        messages.append({"role": "system", "content": f"Conversation context:\n{summary}"})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            endpoint,
            json={
                "model": model,
                "messages": messages,
                "temperature": 0.3,
                "max_tokens": 2048,
            },
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"].get("content", "")
        return content
    except Exception as e:
        return json.dumps({"error": f"Cloud reasoning failed: {e}"}, ensure_ascii=False)


def get_context_usage(args: dict, context=None) -> str:
    """Return context usage stats (tokens used / max)."""
    max_tokens = int(os.environ.get("AIOS_CONTEXT_MAX", "8192"))
    if context:
        total = sum(len(m.get("content", "")) // 4 for m in context)
        pct = min(100, int(total * 100 / max_tokens))
        return json.dumps({"tokens_used": total, "max_tokens": max_tokens, "usage_pct": pct}, ensure_ascii=False)
    return json.dumps({"error": "No context available"}, ensure_ascii=False)


# Handler to execute tools
def execute_tool(name: str, args: dict, context=None) -> str:
    handlers = {
        "run_command": run_command,
        "list_desktop_apps": list_desktop_apps,
        "read_file": read_file,
        "write_file": write_file,
        "web_search": web_search,
        "git_operation": git_operation,
        "mcp_call": mcp_call,
        "run_playbook": run_playbook,
        "process_start": process_start,
        "process_send": process_send,
        "process_close": process_close,
        "process_list": process_list,
        "cloud_reasoning": lambda **kw: cloud_reasoning(kw, context=context),
        "get_context_usage": lambda **kw: get_context_usage(kw, context=context),
        "screenshot": screenshot,
        "ocr": ocr,
        "xdotool_type": xdotool_type,
        "xdotool_key": xdotool_key,
        "xdotool_click": xdotool_click,
    }
    if name not in handlers:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    try:
        return handlers[name](**args)
    except TypeError as e:
        return json.dumps({"error": f"Invalid arguments: {e}"}, ensure_ascii=False)
