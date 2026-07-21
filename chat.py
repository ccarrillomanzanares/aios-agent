#!/usr/bin/env python3
"""Interactive chat with the SRE Agent.
Session persists automatically and input supports history and cursor navigation."""
import readline
import atexit
from pathlib import Path
from agent import Agent

HISTORY_FILE = Path("data/.chat_history")

def main():
    # Enable arrow key navigation and history
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if HISTORY_FILE.exists():
        readline.read_history_file(str(HISTORY_FILE))
    readline.set_history_length(500)
    atexit.register(lambda: readline.write_history_file(str(HISTORY_FILE)))

    agent = Agent()
    print("Agente SRE. Escribe tu consulta o 'salir'.")
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

        response = agent.run(query)
        print(f"\n{response}\n")


if __name__ == "__main__":
    main()
