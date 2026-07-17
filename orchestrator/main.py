#!/usr/bin/env python3
"""Orquestador interactivo SRE: RAG + LLM local + executor seguro + historial + modo plan."""
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "rag"))
from llm_client import LLMClient
from rag_client import RAGClient
from executor import run_command


PROMPTS_PATH = Path(__file__).parent / "prompts.yaml"
MAX_HISTORY_TURNS = 5

# Patrones para detectar correcciones de nombres/palabras en comandos anteriores
CORRECTION_PATTERNS = [
    # "no lynis, lynx" / "no, lynis, lynx"
    r"no[\s,]+(\S+)[\s,]+(\S+)\s*$",
    # "no es lynis, es lynx"
    r"no\s+es\s+(\S+),?\s+es\s+(\S+)",
    # "corrigeme: lynis -> lynx"
    r"corri(?:ge|geme)(?:\s+a)?(?:\s*[:\-]\s*)?\s*(\S+)\s*(?:->|→)\s*(\S+)",
    r"corri(?:ge|geme)(?:\s+a)?(?:\s*[:\-]\s*)?\s*(\S+)",
]


def load_prompts():
    with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def format_context(chunks: list) -> str:
    lines = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk["metadata"]
        lines.append(f"[{i}] {meta.get('source', '?')} | {meta.get('category', '?')}")
        lines.append(chunk["text"])
        lines.append("")
    return "\n".join(lines)


def clean_payload(payload: str) -> str:
    """Limpia backticks y espacios alrededor de un comando."""
    payload = payload.strip()
    if payload.startswith("`") and payload.endswith("`"):
        payload = payload[1:-1].strip()
    return payload


def parse_llm_output(text: str) -> tuple[str, str]:
    text = text.strip()
    if not text:
        return "", ""

    # Buscar etiquetas en cualquier posición para casos donde el modelo
    # las incluye en medio de la respuesta.
    for marker, intent_name, skip in [
        ("PLAN:", "PLAN", 5),
        ("COMMAND:", "COMMAND", 8),
        ("EXPLAIN:", "EXPLAIN", 8),
        ("ASK:", "ASK", 4),
    ]:
        idx = text.find(marker)
        if idx != -1:
            intent = intent_name
            rest = clean_payload(text[idx + skip:])
            # Si PLAN contiene un único comando simple, tratarlo como COMMAND
            if intent == "PLAN":
                lines = [l.strip() for l in rest.splitlines() if l.strip()]
                if len(lines) == 1 and not re.search(r"[;|&\n]", lines[0]):
                    return "COMMAND", lines[0]
            return intent, rest

    upper = text.upper()
    if upper.startswith("PLAN"):
        rest = text[4:].strip()
        lines = [l.strip() for l in rest.splitlines() if l.strip()]
        if len(lines) == 1 and not re.search(r"[;|&\n]", lines[0]):
            return "COMMAND", clean_payload(lines[0])
        return "PLAN", rest
    if upper.startswith("COMMAND"):
        return "COMMAND", clean_payload(text[7:])
    if upper.startswith("EXPLAIN"):
        return "EXPLAIN", clean_payload(text[7:])
    if upper.startswith("ASK"):
        return "ASK", text[3:].strip()
    if upper == "DONE":
        return "DONE", ""
    return "EXPLAIN", text


def parse_plan(text: str) -> list[str]:
    """Extrae pasos numerados de una respuesta PLAN."""
    lines = text.strip().splitlines()
    steps = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Líneas tipo "1. Comando" o "1) Comando" o "- Comando"
        cleaned = re.sub(r"^\s*(\d+[\.\)]|\-)\s*", "", line)
        if cleaned:
            steps.append(cleaned)
    return steps


def build_messages_with_history(prompts: dict, system: str, user_input: str,
                                context: str, history: list[dict]) -> list[dict]:
    messages = [{"role": "system", "content": system}]
    for turn in history[-MAX_HISTORY_TURNS:]:
        messages.append({"role": "user", "content": turn["user"]})
        if turn.get("assistant"):
            messages.append({"role": "assistant", "content": turn["assistant"]})
    user_prompt = prompts["rag_context_template"].format(
        context=context[:2000],
        question=user_input,
    )
    messages.append({"role": "user", "content": user_prompt})
    return messages


def _extract_last_command(assistant_text: str) -> tuple[str, str] | None:
    """Si la última respuesta fue COMMAND, devuelve (intent, comando)."""
    intent, payload = parse_llm_output(assistant_text)
    if intent == "COMMAND" and payload:
        return intent, payload
    return None


def _apply_correction(previous_command: str, user_input: str) -> str | None:
    """Detecta correcciones de nombre y reemplaza en el comando anterior manteniendo la acción."""
    old_word = new_word = None
    for pat in CORRECTION_PATTERNS:
        m = re.search(pat, user_input, re.IGNORECASE)
        if m:
            old_word, new_word = m.group(1), m.group(2)
            break

    if not old_word or not new_word:
        return None

    if old_word.lower() in previous_command.lower():
        return re.sub(re.escape(old_word), new_word, previous_command, count=1, flags=re.IGNORECASE)
    return None


def execute_step(step: str, step_num: int, total: int) -> bool:
    print(f"\n  Paso {step_num}/{total}: {step}")
    result = run_command(step)
    if result["success"]:
        if result["stdout"]:
            print("  --- Salida ---")
            for line in result["stdout"].splitlines():
                print(f"  {line}")
        return True
    else:
        print(f"  ❌ Error: {result['stderr']}")
        return False


def run_plan(steps: list[str]) -> bool:
    print(f"\n📋 Plan con {len(steps)} pasos. Se pedirá aprobación para cada uno.")
    for i, step in enumerate(steps, 1):
        print(f"\n  Paso {i}: {step}")
        answer = input("  ¿Aprobar este paso? [s/n/edit/stop]: ").strip().lower()
        if answer == "edit":
            step = input("  Comando corregido: ").strip()
        elif answer in ("stop", "cancel"):
            print("  Plan cancelado.")
            return False
        elif answer not in ("s", "sí", "si", "y", "yes"):
            print("  Paso omitido.")
            continue
        result = run_command(step, auto_approve_readonly=False)
        if result["success"]:
            if result["stdout"]:
                print("  --- Salida ---")
                for line in result["stdout"].splitlines():
                    print(f"  {line}")
        else:
            print(f"  ❌ Error: {result['stderr']}")
            stop = input("  ¿Continuar con el siguiente paso? [s/n]: ").strip().lower()
            if stop not in ("s", "sí", "si", "y", "yes"):
                print("  Plan cancelado.")
                return False
    print("\n✅ Plan completado.")
    return True


def main():
    prompts = load_prompts()
    rag = RAGClient()
    llm = LLMClient()
    history: list[dict] = []

    print("🤖 SRE-Copilot iniciado. Escribe 'salir' para terminar.")

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nSaliendo...")
            break

        if user_input.lower() in ("salir", "exit", "quit", "q"):
            print("Saliendo...")
            break

        if not user_input:
            continue

        chunks = rag.retrieve(user_input, n_results=5)
        context = format_context(chunks)
        system = prompts["system_prompt"]
        messages = build_messages_with_history(
            prompts, system, user_input, context, history
        )

        try:
            response = llm.chat(messages, temperature=0.2, max_tokens=512)
        except Exception as e:
            print(f"❌ Error llamando al LLM: {e}")
            continue

        intent, payload = parse_llm_output(response)

        # Corrección manual de nombres en comandos: si el usuario corrige un
        # nombre/palabra del comando anterior, reemplazarlo manteniendo la acción.
        if history and intent in ("EXPLAIN", "ASK"):
            last_cmd = _extract_last_command(history[-1].get("assistant", ""))
            if last_cmd:
                corrected = _apply_correction(last_cmd[1], user_input)
                if corrected:
                    intent, payload = "COMMAND", corrected

        # Corrección directa sin depender del LLM: patrones como "no X, Y".
        if history and intent == "COMMAND":
            last_cmd = _extract_last_command(history[-1].get("assistant", ""))
            if last_cmd:
                corrected = _apply_correction(last_cmd[1], user_input)
                if corrected:
                    payload = corrected

        if not intent:
            print(f"\n❓ No entendí la respuesta del modelo. ¿Puedes reformular?")
            continue

        assistant_text = response
        if intent == "COMMAND":
            assistant_text = f"COMMAND: {payload}"
        elif intent == "EXPLAIN":
            assistant_text = f"EXPLAIN: {payload}"
        elif intent == "ASK":
            assistant_text = f"ASK: {payload}"
        elif intent == "PLAN":
            assistant_text = f"PLAN: {payload}"
        elif intent == "DONE":
            assistant_text = "DONE"

        history.append({"user": user_input, "assistant": assistant_text})

        if intent == "EXPLAIN":
            print(f"\n💡 {payload}")
        elif intent == "ASK":
            print(f"\n❓ {payload}")
        elif intent == "DONE":
            print("\n✅ Hecho.")
        elif intent == "PLAN":
            steps = parse_plan(payload)
            if not steps:
                print("\n⚠️  No se pudieron extraer pasos del plan.")
                continue
            run_plan(steps)
        elif intent == "COMMAND":
            print(f"\n⚙️  Comando propuesto: {payload}")
            if not payload:
                print("\n⚠️  El comando propuesto está vacío.")
                continue
            result = run_command(payload)
            if result["success"]:
                if result["stdout"]:
                    print("\n--- Salida ---")
                    print(result["stdout"])
                else:
                    print("\n✅ Comando ejecutado sin salida.")
            else:
                print(f"\n❌ Error: {result['stderr']}")
        else:
            print(f"\n🤔 Respuesta del modelo no reconocida:\n{response}")


if __name__ == "__main__":
    main()
