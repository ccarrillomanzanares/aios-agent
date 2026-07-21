"""Tools para el agente SRE — función calling nativo."""
import json
import subprocess
import time
from pathlib import Path

import requests

def run_command(command: str, timeout: int = 30, retry: bool = True) -> str:
    """Ejecuta comando shell. Devuelve JSON con stdout, stderr, exit_code, elapsed.

    Si retry=True, intenta recuperarse de errores comunes de apt:
    - "lock" / "Unable to lock" -> espera 3s y reintenta el mismo comando.
    - "Could not get lock" -> prueba con `sudo apt-get` como alternativa.
    Se respeta el timeout total.
    """
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

            # Recuperación de errores comunes de apt
            if retry and r.returncode != 0 and ("apt" in current_command or "apt-get" in current_command):
                lower_err = (stdout + "\n" + stderr).lower()
                if "lock" in lower_err or "unable to lock" in lower_err:
                    if attempts < max_attempts:
                        if "could not get lock" in lower_err and not current_command.startswith("sudo apt-get"):
                            # Reemplaza apt por sudo apt-get si aplica
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

    # Si se agotaron los reintentos
    return json.dumps({"stdout": "", "stderr": "Se agotaron los reintentos", "exit_code": -1,
                      "elapsed": round(time.time() - t0, 2)}, ensure_ascii=False)

def read_file(path: str) -> str:
    """Lee archivo. Devuelve JSON con contenido o error."""
    try:
        p = Path(path).resolve()
        if not p.exists():
            return json.dumps({"error": f"No existe: {path}"}, ensure_ascii=False)
        content = p.read_text(encoding="utf-8", errors="replace")
        return json.dumps({"path": str(p), "content": content[:3000], "size": len(content)}, ensure_ascii=False)
    except PermissionError:
        return json.dumps({"error": f"Permiso denegado: {path}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

def write_file(path: str, content: str) -> str:
    """Escribe archivo. Advierte si es ruta de sistema."""
    try:
        p = Path(path).resolve()
        # Advertir sobre rutas de sistema
        danger_zones = ["/etc/", "/boot/", "/sys/", "/proc/", "/dev/"]
        for zone in danger_zones:
            if str(p).startswith(zone):
                return json.dumps({"warning": f"⚠️ Ruta de sistema ({zone}). Escritura bloqueada.",
                                  "path": str(p)}, ensure_ascii=False)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return json.dumps({"ok": True, "path": str(p), "size": len(content)}, ensure_ascii=False)
    except PermissionError:
        return json.dumps({"error": f"Permiso denegado: {path}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def web_search(query: str, limit: int = 3) -> str:
    """Busca en internet vía Firecrawl local (puerto 3002). Devuelve JSON con resultados."""
    url = "http://localhost:3002/v1/search"
    payload = {"query": query, "limit": limit}
    try:
        r = requests.post(url, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        # Normalizar resultados: lista de {title, url, description}
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
            # Firecrawl /v1/search puede devolver {data: [...]}
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
        return json.dumps({"error": "No se pudo conectar con Firecrawl en localhost:3002. ¿Está levantado?", "details": str(e)}, ensure_ascii=False)
    except requests.exceptions.Timeout:
        return json.dumps({"error": "Timeout al contactar Firecrawl (30s)"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Error en web_search: {e}"}, ensure_ascii=False)


def git_operation(op: str, args: str = "") -> str:
    """Ejecuta operaciones git permitidas en /home/ccmai/sre-agent/. Devuelve JSON."""
    repo = "/home/ccmai/sre-agent"
    op = op.strip().lower()
    allowed = {"status", "commit", "push", "diff", "log"}
    rejected = {"reset", "rebase", "merge", "stash"}

    if op in rejected:
        return json.dumps({"error": f"Operación git '{op}' no permitida por seguridad"}, ensure_ascii=False)
    if op not in allowed:
        return json.dumps({"error": f"Operación git desconocida: {op}. Permitidas: {', '.join(sorted(allowed))}"}, ensure_ascii=False)

    # Rechazar branch -D dentro de args
    lowered = args.lower()
    if "branch" in lowered and ("-d" in lowered or "-delete" in lowered or "-D" in args):
        return json.dumps({"error": "Eliminar ramas (branch -D/-d) no está permitido"}, ensure_ascii=False)

    command_parts = ["git", "-C", repo, op]
    if args:
        command_parts.append(args)
    command = " ".join(command_parts)

    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        stdout = r.stdout.strip()
        stderr = r.stderr.strip()
        # Commit sin mensaje no es válido
        if op == "commit" and (not args or "-m" not in args):
            return json.dumps({"error": "commit requiere mensaje (-m)"}, ensure_ascii=False)
        return json.dumps({"stdout": stdout[:2000], "stderr": stderr[:2000], "exit_code": r.returncode}, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"stdout": "", "stderr": "Timeout (30s)", "exit_code": 124}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"stdout": "", "stderr": str(e), "exit_code": -1}, ensure_ascii=False)


def mcp_call(server: str, tool: str, args: str = "{}") -> str:
    """Llama a un tool de un servidor MCP vía HTTP. Devuelve JSON."""
    try:
        parsed_args = json.loads(args) if args else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"args no es JSON válido: {e}"}, ensure_ascii=False)

    # Soporta server como URL completa o como host base
    if server.startswith("http://") or server.startswith("https://"):
        base = server.rstrip("/")
    else:
        base = f"http://{server}"

    # Intentar endpoints comunes MCP HTTP
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
            # 404 o 405 indica que el endpoint no existe; probamos el siguiente
            if r.status_code in (404, 405):
                last_error = f"{endpoint} → {r.status_code}"
                continue
            r.raise_for_status()
            return json.dumps({"server": server, "tool": tool, "endpoint": endpoint, "result": r.json() if r.text else {}}, ensure_ascii=False)
        except requests.exceptions.ConnectionError as e:
            last_error = f"No se pudo conectar con {server}: {e}"
            break
        except requests.exceptions.Timeout:
            last_error = f"Timeout conectando a {server}"
            break
        except Exception as e:
            last_error = f"{endpoint} → {e}"
            continue
    return json.dumps({"error": f"MCP server no respondió o tool '{tool}' no existe", "details": last_error}, ensure_ascii=False)


# Schemas para function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Ejecuta un comando shell en Linux. Usa para: ver estado del sistema, instalar paquetes, gestionar servicios, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Comando shell a ejecutar"},
                    "timeout": {"type": "integer", "description": "Timeout en segundos (default 30)"},
                    "retry": {"type": "boolean", "description": "Activar reintentos ante errores comunes de apt (default true)"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lee el contenido de un archivo del sistema. Usa para: ver logs, configuraciones, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta absoluta del archivo a leer"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Escribe contenido en un archivo. Bloquea rutas de sistema (/etc, /boot, /sys).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Ruta absoluta donde escribir"},
                    "content": {"type": "string", "description": "Contenido a escribir"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Busca información en internet para resolver dudas técnicas. Usa cuando no sepas la respuesta o necesites documentación actualizada.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Consulta de búsqueda"},
                    "limit": {"type": "integer", "description": "Número máximo de resultados (default 3)"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_operation",
            "description": "Ejecuta operaciones git permitidas (status, commit, push, diff, log) en el repositorio /home/ccmai/sre-agent/.",
            "parameters": {
                "type": "object",
                "properties": {
                    "op": {"type": "string", "description": "Operación git: status, commit, push, diff, log"},
                    "args": {"type": "string", "description": "Argumentos adicionales para git"}
                },
                "required": ["op"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "mcp_call",
            "description": "Llama a un tool de un servidor MCP vía HTTP. Usa para integrar con servidores MCP externos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "server": {"type": "string", "description": "URL o host:puerto del servidor MCP"},
                    "tool": {"type": "string", "description": "Nombre del tool a invocar"},
                    "args": {"type": "string", "description": "Argumentos del tool en JSON (default {})"}
                },
                "required": ["server", "tool"]
            }
        }
    }
]

# Handler para ejecutar tools
def execute_tool(name: str, args: dict) -> str:
    handlers = {
        "run_command": run_command,
        "read_file": read_file,
        "write_file": write_file,
        "web_search": web_search,
        "git_operation": git_operation,
        "mcp_call": mcp_call,
    }
    if name not in handlers:
        return json.dumps({"error": f"Tool desconocida: {name}"}, ensure_ascii=False)
    try:
        return handlers[name](**args)
    except TypeError as e:
        return json.dumps({"error": f"Argumentos inválidos: {e}"}, ensure_ascii=False)
