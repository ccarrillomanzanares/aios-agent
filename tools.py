"""Tools para el agente SRE — función calling nativo."""
import json
import subprocess
import time
from pathlib import Path

def run_command(command: str, timeout: int = 30) -> str:
    """Ejecuta comando shell. Devuelve JSON con stdout, stderr, exit_code, elapsed."""
    t0 = time.time()
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        stdout = r.stdout.strip()[:2000]
        stderr = r.stderr.strip()[:2000]
        return json.dumps({"stdout": stdout, "stderr": stderr, "exit_code": r.returncode,
                          "elapsed": round(time.time() - t0, 2)}, ensure_ascii=False)
    except subprocess.TimeoutExpired:
        return json.dumps({"stdout": "", "stderr": f"Timeout ({timeout}s)", "exit_code": 124,
                          "elapsed": timeout}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"stdout": "", "stderr": str(e), "exit_code": -1, "elapsed": 0}, ensure_ascii=False)

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
                    "timeout": {"type": "integer", "description": "Timeout en segundos (default 30)"}
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
    }
]

# Handler para ejecutar tools
def execute_tool(name: str, args: dict) -> str:
    handlers = {"run_command": run_command, "read_file": read_file, "write_file": write_file}
    if name not in handlers:
        return json.dumps({"error": f"Tool desconocida: {name}"}, ensure_ascii=False)
    try:
        return handlers[name](**args)
    except TypeError as e:
        return json.dumps({"error": f"Argumentos inválidos: {e}"}, ensure_ascii=False)
