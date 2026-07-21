"""Tools for the SRE agent — native function calling."""
import json
import sys
import re
import signal
import subprocess
import time
from pathlib import Path

import requests
import yaml
from playbook import run_playbook

def _is_blocked_command(command: str) -> bool:
    """Return True if command matches an unconditionally blocked dangerous pattern."""
    lower = command.lower()
    # rm -rf / or rm -rf /* (root destruction only; allow rm -rf /tmp/...)
    if re.search(r"rm\s+-rf\s+/\s*$", lower) or        re.search(r"rm\s+-rf\s+/\*", lower):
        return True
    if re.search(r"dd\s+if=\S+\s+of=/dev/\S+", lower):
        return True
    if re.search(r"mkfs\.\w+\s+\S+", lower):
        return True
    if re.search(r"fdisk", lower):
        return True
    if re.search(r"chmod.*(?:-r\s+)?000", lower):
        return True
    return False


def _is_destructive_command(command: str) -> bool:
    """Return True if command requires human confirmation before execution."""
    lower = command.lower()
    if re.search(r"rm\s+-rf", lower):
        return True
    if re.search(r"sudo\s+rm", lower):
        return True
    if re.search(r">\s*/dev/sd[a-z]", lower):
        return True
    if re.search(r"format", lower):
        return True
    if re.search(r"dd\s+if=\S+", lower):
        return True
    return False


def _confirm_destructive(command: str, timeout: int = 10) -> bool:
    """Ask user for confirmation before running a destructive command."""
    print(f"⚠️ Destructive command detected: {command}. Continue? (y/N): ", file=sys.stderr, end="", flush=True)
    try:
        def _timeout_handler(signum, frame):
            raise TimeoutError
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)
        try:
            answer = sys.stdin.readline().strip()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
        return answer in ("y", "Y")
    except TimeoutError:
        print("Confirmation timeout", file=sys.stderr)
        return False
    except Exception:
        return False


def run_command(command: str, timeout: int = 30, retry: bool = True) -> str:
    """Execute a shell command. Returns JSON with stdout, stderr, exit_code, elapsed.

    If retry=True, recover from common apt errors:
    - "lock" / "Unable to lock" -> wait 3s and retry the same command.
    - "Could not get lock" -> try `sudo apt-get` as an alternative.
    Total timeout is respected.
    """
    # Tool allowlist: block unconditionally dangerous commands
    if _is_blocked_command(command):
        return json.dumps({"error": "Command blocked: dangerous operation", "exit_code": -1,
                          "stdout": "", "stderr": "Blocked for security reasons"}, ensure_ascii=False)

    # Human-in-the-loop for high-risk but not blocked commands
    if _is_destructive_command(command):
        if not _confirm_destructive(command):
            return json.dumps({"error": "Command cancelled by user", "exit_code": -1,
                              "stdout": "", "stderr": "Cancelled by user"}, ensure_ascii=False)

    t0 = time.time()
    attempts = 0
    max_attempts = 3
    current_command = command

    while attempts < max_attempts:
        attempts += 1
        elapsed = time.time() - t0
        remaining = max(0.1, timeout - elapsed)
        try:
            r = subprocess.run(current_command, shell=True, capture_output=True, text=True, timeout=remaining)
            stdout = r.stdout.strip()[:2000]
            stderr = r.stderr.strip()[:2000]

            # Recover from common apt errors
            if retry and r.returncode != 0 and ("apt" in current_command or "apt-get" in current_command):
                lower_err = (stdout + "\n" + stderr).lower()
                if "lock" in lower_err or "unable to lock" in lower_err:
                    if attempts < max_attempts:
                        if "could not get lock" in lower_err and not current_command.startswith("sudo apt-get"):
                            # Replace apt with sudo apt-get if applicable
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

    # Retries exhausted
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
        # Warn about system paths
        danger_zones = ["/etc/", "/boot/", "/sys/", "/proc/", "/dev/"]
        for zone in danger_zones:
            if str(p).startswith(zone):
                return json.dumps({"warning": f"⚠️ System path ({zone}). Write blocked.",
                                  "path": str(p)}, ensure_ascii=False)
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
        # Normalize results: list of {title, url, description}
        results = []
        if isinstance(data, list):
            for item in data[:limit]:
                if isinstance(item, dict):
                    results.append({
                        "title": item.get("title", item.get("name", "")),
                        "url": item.get("url", item.get("link", "")),
                        "description": item.get("description", item.get("snippet", item.get("content", ""))),
                    })
        elif isinstance(data, dict):
            # Firecrawl /v1/search may return {data: [...]}
            candidates = data.get("data", data.get("results", []))
            for item in candidates[:limit]:
                if isinstance(item, dict):
                    results.append({
                        "title": item.get("title", item.get("name", "")),
                        "url": item.get("url", item.get("link", "")),
                        "description": item.get("description", item.get("snippet", item.get("content", ""))),
                    })
        return json.dumps({"query": query, "count": len(results), "results": results}, ensure_ascii=False)
    except requests.exceptions.ConnectionError as e:
        return json.dumps({"error": "Could not connect to Firecrawl at localhost:3002. Is it running?", "details": str(e)}, ensure_ascii=False)
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
        return json.dumps({"error": f"Git operation '{op}' not allowed for security"}, ensure_ascii=False)
    if op not in allowed:
        return json.dumps({"error": f"Unknown git operation: {op}. Allowed: {', '.join(sorted(allowed))}"}, ensure_ascii=False)

    # Reject branch -D inside args
    lowered = args.lower()
    if "branch" in lowered and ("-d" in lowered or "-delete" in lowered or "-D" in args):
        return json.dumps({"error": "Deleting branches (branch -D/-d) is not allowed"}, ensure_ascii=False)

    command_parts = ["git", "-C", repo, op]
    if args:
        command_parts.append(args)
    command = " ".join(command_parts)

    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()
        # Commit without message is invalid
        if op == "commit" and (not args or "-m" not in args):
            return json.dumps({"error": "commit requires a message (-m)"}, ensure_ascii=False)
        return json.dumps({"stdout": stdout[:2000], "stderr": stderr[:2000], "exit_code": r.returncode}, ensure_ascii=False)
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

    # Supports server as full URL or base host
    if server.startswith("http://") or server.startswith("https://"):
        base = server.rstrip("/")
    else:
        base = f"http://{server}"

    # Try common MCP HTTP endpoints
    endpoints = [
        f"{base}/v1/tools/{tool}",
        f"{base}/tools/{tool}",
        f"{base}/mcp/{tool}",
        f"{base}/{tool}",
    ]
    last_error = ""
    for endpoint in endpoints:
        try:
            r = requests.post(endpoint, json=parsed_args, timeout=15)
            # 404 or 405 means the endpoint does not exist; try the next one
            if r.status_code in (404, 405):
                last_error = f"{endpoint} → {r.status_code}"
                continue
            r.raise_for_status()
            return json.dumps({"server": server, "tool": tool, "endpoint": endpoint, "result": r.json() if r.text else {}}, ensure_ascii=False)
        except requests.exceptions.ConnectionError as e:
            last_error = f"Could not connect to {server}: {e}"
            break
        except requests.exceptions.Timeout:
            last_error = f"Timeout connecting to {server}"
            break
        except Exception as e:
            last_error = f"{endpoint} → {e}"
            continue
    return json.dumps({"error": f"MCP server did not respond or tool '{tool}' does not exist", "details": last_error}, ensure_ascii=False)


# Schemas for function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Execute a shell command on Linux. Use for: checking system status, installing packages, managing services, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
                    "retry": {"type": "boolean", "description": "Enable retries on common apt errors (default true)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file on the system. Use for: viewing logs, configurations, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path of the file to read"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file. Blocks system paths (/etc, /boot, /sys).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path where to write"},
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
            "description": "Search the web to resolve technical questions. Use when you do not know the answer or need up-to-date documentation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Maximum number of results (default 3)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_operation",
            "description": "Run allowed git operations (status, commit, push, diff, log) in the /home/ccmai/sre-agent/ repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "description": "Git operation: status, commit, push, diff, log"},
                    "args": {"type": "string", "description": "Additional arguments for git"}
                },
                "required": ["op"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_call",
            "description": "Call a tool on an MCP server via HTTP. Use to integrate with external MCP servers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "URL or host:port of the MCP server"},
                    "tool": {"type": "string", "description": "Name of the tool to invoke"},
                    "args": {"type": "string", "description": "Tool arguments as JSON (default {})"}
                },
                "required": ["server", "tool"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_playbook",
            "description": "Read a YAML playbook and execute its steps sequentially, verifying each step. Use for: multi-step installation, configuration or maintenance workflows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute path to the .yml/.yaml playbook file"}
                },
                "required": ["path"]
            }
        }
    }
]

# Handler to execute tools
def execute_tool(name: str, args: dict) -> str:
    handlers = {
        "run_command": run_command,
        "read_file": read_file,
        "write_file": write_file,
        "web_search": web_search,
        "git_operation": git_operation,
        "mcp_call": mcp_call,
        "run_playbook": run_playbook,
    }
    if name not in handlers:
        return json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)
    try:
        return handlers[name](**args)
    except TypeError as e:
        return json.dumps({"error": f"Invalid arguments: {e}"}, ensure_ascii=False)
