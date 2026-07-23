import json
import os
import re
from pathlib import Path
import requests

# Config from environment (set by chat.py)
LLAMA_SERVER = os.environ.get("AIOS_LLAMA_SERVER", "http://localhost:8083/v1/chat/completions")
API_KEY = os.environ.get("AIOS_API_KEY", "")
AIOS_MODE = os.environ.get("AIOS_MODE", "local")
CLOUD_MODEL = os.environ.get("AIOS_CLOUD_MODEL", "")
CLOUD_HEADERS = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

MAX_TOKENS = 512
TEMPERATURE = 0.1
MAX_TURNS = 10
# Compression: 95% for local (8K), 50% for cloud (per-provider context_limit)
_LOCAL_CONTEXT = 8192
_cloud_context = int(os.environ.get("AIOS_CLOUD_CONTEXT", "128000"))
MAX_HISTORY_TOKENS = int(_LOCAL_CONTEXT * 0.95) if os.environ.get("AIOS_MODE") == "local" else int(_cloud_context * 0.50)
SESSION_FILE = Path("data/session.json")


def _estimate_tokens(text: str) -> int:
    """Estimate tokens via llama.cpp tokenize endpoint (accurate)."""
    try:
        resp = requests.post(
            LLAMA_SERVER + "/tokenize",
            json={"content": text},
            timeout=5
        )
        if resp.status_code == 200:
            return len(resp.json().get("tokens", []))
    except Exception:
        pass
    # Fallback: rough estimate
    return len(text) // 2


SYSTEM_PROMPT = """Eres un sysadmin Linux experto. Puedes ejecutar comandos, leer y escribir archivos.
Responde en español. Sé conciso.
Si ejecutas un comando, muestra el resultado al usuario.
Antes de comandos destructivos (rm -rf, dd, mkfs, fdisk), advierte y pide confirmación.
Si no sabes algo, dilo honestamente: 'No lo sé'.
No uses etiquetas <think>.

Para tareas complejas, NO expliques — EJECUTA. Genera un plan con pasos numerados y ejecuta cada paso automáticamente, verificando el resultado antes de continuar.
Ejemplo:
  Usuario: "instala WordPress con Docker y MariaDB"
  Agente: ejecuta paso 1 (verificar Docker), paso 2 (crear compose), paso 3 (levantar), paso 4 (verificar). Sin preguntar, sin explicar. Solo ejecuta.

Si un script espera entrada interactiva (input(), confirmaciones, contraseñas), usa process_start. NO uses run_command para scripts interactivos."""

from tools import TOOLS, execute_tool
from memory import ProceduralMemory


class Agent:
    def __init__(self):
        self.memory = ProceduralMemory()
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._load_session()

    def _quick_llm(self, prompt: str, tokens: int = 20, temp: float = 0.0) -> str:
        """LLM rápido sin tools, para generación de claves y compresión."""
        resp = requests.post(
            LLAMA_SERVER,
            json={"messages": [{"role": "user", "content": f"/no_think {prompt}"}],
                  "max_tokens": tokens, "temperature": temp},
            headers=CLOUD_HEADERS,
            timeout=15
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def _count_tokens(self, texts: list[str]) -> int:
        """Estimación burda: 4 chars ≈ 1 token."""
        return sum(len(t) // 4 for t in texts)

    def _compress(self):
        """Compress history when approaching context limit. Keeps system prompt + last 3 exchanges."""
        all_text = "\n".join(m.get("content", "") for m in self.messages)
        total = _estimate_tokens(all_text)
        if total < MAX_HISTORY_TOKENS:
            return
        keep = [self.messages[0]]
        if len(self.messages) > 6:
            old = self.messages[1:-6]
            history_str = "\n".join(
                f"{m['role']}: {m['content'][:200]}" for m in old if m.get("content")
            )
            try:
                summary = self._quick_llm(
                    f"Resume the following conversation in 2-3 sentences keeping only technical details:\n\n{history_str}",
                    tokens=100, temp=0.3
                )
                keep.append({"role": "system", "content": f"[Summary: {summary}]"})
            except Exception:
                keep.append({"role": "system", "content": "[Previous conversation compressed]"})
            keep.extend(self.messages[-6:])
        else:
            keep = self.messages
        self.messages = keep

    def _save_session(self):
        """Guarda el historial de la conversación al salir."""
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False)

    def _load_session(self):
        """Carga el historial de la conversación anterior."""
        if SESSION_FILE.exists():
            try:
                old = json.loads(SESSION_FILE.read_text())
                # Mantener system prompt original, concatenar historial cargado
                loaded_messages = [m for m in old if m["role"] != "system"]
                self.messages.extend(loaded_messages)
                # Comprimir si el historial cargado es muy largo
                texts = [m.get("content", "") for m in self.messages]
                if self._count_tokens(texts) > MAX_HISTORY_TOKENS:
                    self._compress()
                print(f"  [Sesión reanudada: {len(loaded_messages)} mensajes anteriores]")
            except Exception:
                pass

    def _clean(self, text: str) -> str:
        """Limpia think blocks y normaliza."""
        text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()
        return text

    def run(self, query: str) -> str:
        """Procesa una consulta con function calling loop. Primero busca en memoria procedural."""
        # Comprimir historial si es necesario
        self._compress()

        # 1. Buscar en caché procedural
        cached = self.memory.find(query, self._quick_llm)
        if cached:
            return f"[cache] {cached}"

        self.messages.append({"role": "user", "content": f"/no_think {query}"})

        final_response = ""
        for _ in range(MAX_TURNS):
            payload = {
                "messages": self.messages,
                "tools": TOOLS,
                "temperature": TEMPERATURE,
                "max_tokens": MAX_TOKENS,
            }
            if AIOS_MODE in ("cloud", "hybrid") and CLOUD_MODEL:
                payload["model"] = CLOUD_MODEL

            try:
                resp = requests.post(LLAMA_SERVER, json=payload, headers=CLOUD_HEADERS, timeout=120)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                return f"Error de conexión al LLM: {e}"

            choice = data["choices"][0]
            msg = choice["message"]
            finish = choice.get("finish_reason", "")

            # Tool call → ejecutar y devolver resultado al LLM
            if finish == "tool_calls" or msg.get("tool_calls"):
                assistant_msg = {"role": "assistant", "content": msg.get("content") or ""}
                if msg.get("tool_calls"):
                    assistant_msg["tool_calls"] = msg["tool_calls"]
                self.messages.append(assistant_msg)

                for tc in msg.get("tool_calls", []):
                    func = tc["function"]
                    name = func["name"]
                    try:
                        args = json.loads(func["arguments"])
                    except json.JSONDecodeError:
                        args = {}
                    result = execute_tool(name, args)
                    print(f"  🔧 {name}({func.get('arguments','')})")
                    if name == "run_command":
                        r = json.loads(result)
                        print(f"     stdout: {r.get('stdout','')[:150]}")
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", "call_0"),
                        "content": result
                    })
                continue  # siguiente iteración: LLM procesa el resultado

            # Respuesta final (texto)
            if msg.get("content"):
                final_response = self._clean(msg["content"])
                self.messages.append({"role": "assistant", "content": final_response})
                # If tools were used, store in procedural memory (only static knowledge)
                had_tools = any(m["role"] == "tool" for m in self.messages[-5:])
                had_dynamic = any("run_command" in m.get("content","") or "read_file" in m.get("content","")
                                  for m in self.messages[-5:])
                if had_tools and not had_dynamic and final_response and final_response != "No lo sé":
                    self.memory.store(query, final_response, self._quick_llm)
                self._save_session()
                break
            else:
                final_response = "(respuesta vacía del modelo)"
                break

        return final_response or "(sin respuesta)"

    def reset(self):
        """Reinicia la conversación."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
