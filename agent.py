"""Agente SRE ligero — function calling con Qwen3-8B."""
import json
import re
import requests

LLAMA_SERVER = "http://localhost:8083/v1/chat/completions"
MAX_TOKENS = 512
TEMPERATURE = 0.1
MAX_TURNS = 5

SYSTEM_PROMPT = """Eres un sysadmin Linux experto. Puedes ejecutar comandos, leer y escribir archivos.
Responde en español. Sé conciso.
Si ejecutas un comando, muestra el resultado al usuario.
Antes de comandos destructivos (rm -rf, dd, mkfs, fdisk), advierte y pide confirmación.
Si no sabes algo, dilo honestamente: 'No lo sé'.
No uses etiquetas <think>."""

from tools import TOOLS, execute_tool


class Agent:
    def __init__(self):
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _clean(self, text: str) -> str:
        """Limpia think blocks y normaliza."""
        text = re.sub(r"<think>.*?</think>\s*", "", text, flags=re.DOTALL).strip()
        return text

    def run(self, query: str) -> str:
        """Procesa una consulta con function calling loop."""
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
                break
            else:
                final_response = "(respuesta vacía del modelo)"
                break

        return final_response or "(sin respuesta)"

    def reset(self):
        """Reinicia la conversación."""
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
