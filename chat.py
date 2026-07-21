#!/usr/bin/env python3
"""Chat interactivo con el agente SRE.
La sesión se guarda automáticamente al salir y se reanuda al arrancar."""
import json
from pathlib import Path

from agent import Agent
from tools import execute_tool


def handle_slash(agent: Agent, query: str) -> bool:
    """Procesa comandos slash. Devuelve True si el comando fue consumido."""
    cmd = query.strip()
    lowered = cmd.lower()

    if lowered == "/retry":
        # Elimina el último intercambio del historial (user + assistant/tool)
        if len(agent.messages) <= 1:
            print("  [No hay intercambios para reintentar]")
        else:
            removed = []
            # Borrar en orden inverso hasta consumir un intercambio completo
            while len(agent.messages) > 1:
                last = agent.messages.pop()
                removed.append(last["role"])
                if last["role"] == "user":
                    break
            print(f"  [Último intercambio eliminado ({', '.join(removed)})]")
        return True

    if lowered == "/save":
        agent._save_session()
        from agent import SESSION_FILE
        print(f"  [Sesión guardada en {SESSION_FILE}]")
        return True

    if lowered == "/clear":
        system = agent.messages[0] if agent.messages else {"role": "system", "content": ""}
        agent.messages = [system]
        print("  [Historial borrado; system prompt conservado]")
        return True

    if lowered == "/stats":
        total_msgs = len(agent.messages)
        memory_count = len(agent.memory.skills) if agent.memory else 0
        from agent import SESSION_FILE
        session_file = Path(SESSION_FILE)
        session_size = session_file.stat().st_size if session_file.exists() else 0
        print(f"  [Stats] mensajes: {total_msgs}, skills en memoria: {memory_count}, session.json: {session_size} bytes")
        return True

    if lowered.startswith("/git"):
        parts = cmd.split(None, 1)
        if len(parts) == 1 or parts[1].strip() == "":
            op = "status"
            args = ""
        else:
            rest = parts[1].strip()
            # /git status
            if rest.startswith("status"):
                op = "status"
                args = rest[len("status"):].strip()
            elif " " in rest:
                op, args = rest.split(None, 1)
            else:
                op = rest
                args = ""
        result = execute_tool("git_operation", {"op": op, "args": args})
        try:
            parsed = json.loads(result)
            print(f"  [git {op} {args}] exit_code={parsed.get('exit_code')}")
            if parsed.get("stdout"):
                print(f"  stdout:\n{parsed['stdout']}")
            if parsed.get("stderr"):
                print(f"  stderr:\n{parsed['stderr']}")
        except Exception as e:
            print(f"  [Error ejecutando git_operation: {e}]")
        return True

    return False


def main():
    agent = Agent()
    print("Agente SRE. Escribe tu consulta o 'salir'.")
    print("Comandos: /retry /save /clear /stats /git [status|diff|...]")
    print("El agente puede ejecutar comandos, leer y escribir archivos.\n")

    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            agent._save_session()
            print("\n¡Hasta luego!")
            break

        if not query:
            continue
        if query.lower() in ("salir", "exit", "quit"):
            agent._save_session()
            print("¡Hasta luego!")
            break

        # Procesar slash commands antes de enviar al agente
        if query.startswith("/") and handle_slash(agent, query):
            continue

        response = agent.run(query)
        print(f"\n{response}\n")


if __name__ == "__main__":
    main()
