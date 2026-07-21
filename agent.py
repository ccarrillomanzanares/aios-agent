"""Lightweight SRE Agent — native function calling with Qwen3-8B."""
import json
import re
from pathlib import Path
import requests

LLAMA_SERVER = "http://localhost:8083/v1/chat/completions"
MAX_TOKENS = 512
TEMPERATURE = 0.1
MAX_TURNS = 10
MAX_HISTORY_TOKENS = 6000
SESSION_FILE = Path("data/session.json")


SYSTEM_PROMPT = """Eres un sysadmin Linux experto. Puedes ejecutar comandos, leer y escribir archivos.
Responde en español. Sé conciso.
Si ejecutas un comando, muestra el resultado al usuario.
Antes de comandos destructivos (rm -rf, dd, mkfs, fdisk), advierte y pide confirmación.
Si no sabes algo, dilo honestamente: 'No lo sé'.
No uses etiquetas <think>.

Para tareas complejas, NO expliques — EJECUTA. Genera un plan con pasos numerados y ejecuta cada paso automáticamente, verificando el resultado antes de continuar.
Ejemplo:
  Usuario: "instala WordPress con Docker y MariaDB"
  Agente: ejecuta paso 1 (verificar Docker), paso 2 (crear compose), paso 3 (levantar), paso 4 (verificar). Sin preguntar, sin explicar. Solo ejecuta."""

from tools import TOOLS, execute_tool
from memory import ProceduralMemory


class Agent:
    def __init__(self):
        self.memory = ProceduralMemory()
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._load_session()

    def _quick_llm(self, prompt: str, tokens: int = 20, temp: float = 0.0) -> str:
        """Fast LLM call without tools, used for key generation and compression."""
        resp = requests.post(
            LLAMA_SERVER,
            json={"messages": [{"role": "user", "content": f"/no_think {prompt}"}],
                  "max_tokens": tokens, "temperature": temp},
            timeout=15
        )
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()

    def _count_tokens(self, texts: list[str]) -> int:
        """Rough token estimator: 4 chars ≈ 1 token."""
        return sum(len(t) // 4 for t in texts)

    def _compress(self):
        """Compress history when it exceeds the token limit."""
        texts = [m.get("content", "") for m in self.messages]
        if self._count_tokens(texts) < MAX_HISTORY_TOKENS:
            return
        # Keep system prompt + last 3 exchanges (6 messages)
        keep = [self.messages[0]]
        if len(self.messages) > 6:
            old = self.messages[1:-6]
            history_str = "\n".join(
                f"{m['role']}: {m['content'][:200]}" for m in old if m.get("content")
            )
            try:
                summary = self._quick_llm(
                    f"Resume la siguiente conversación en 2-3 frases, capturando solo información técnica relevante:\n\n{history_str}",
                    tokens=100, temp=0.3
                )
                keep.append({"role": "system", "content": f"[Resumen de conversación anterior: {summary}]"})
            except Exception:
                keep.append({"role": "system", "content": "[Conversación anterior omitida por error de compresión]"})
            keep.extend(self.messages[-6:])
        else:
            keep = self.messages
        self.messages = keep

    def _save_session(self):
        """Save conversation history on exit."""
        SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False)

    def _load_session(self):
        """Load previous conversation history."""
        if SESSION_FILE.exists():
            try:
                old = json.loads(SESSION_FILE.read_text())
                # Keep original system prompt, append loaded history
                loaded_messages = [m for m in old if m["role"] != "system"]
                self.messages.extend(loaded_messages)
                # Compress if loaded history is too long
                texts = [m.get("content", "") for m in self.messages]
                if self._count_tokens(texts) > MAX_HISTORY_TOKENS:
                    self._compress()
                print(f"  [Sesión reanudada: {len(loaded_messages)} mensajes anteriores]")
            except Exception:
                pass

    def _clean(self, text: str) -> str:
        """Clean think blocks and normalize."""
        text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()
        return text

    def run(self, query: str) -> str:
        """Process a query with a function-calling loop. First checks procedural memory."""
        # Compress history if needed
        self._compress()

        # 1. Search procedural cache
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

            try:
                resp = requests.post(LLAMA_SERVER, json=payload, timeout=120)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                return f"Error de conexión al LLM: {e}"

            choice = data["choices"][0]
            msg = choice["message"]
            finish = choice.get("finish_reason", "")

            # Tool call → execute and return result to LLM
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
                continue  # next iteration: LLM processes the result

            # Final response (text)
            if msg.get("content"):
                final_response = self._clean(msg["content"])
                self.messages.append({"role": "assistant", "content": final_response})
                # If tools were used, store in procedural memory
                had_tools = any(m["role"] == "tool" for m in self.messages[-5:])
                if had_tools and final_response and final_response != "No lo sé":
                    self.memory.store(query, final_response, self._quick_llm)
                self._save_session()
                break
            else:
                final_response = "(respuesta vacía del modelo)"
                break

        return final_response or "(sin respuesta)"

    def reset(self):
        """Reset conversation."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
