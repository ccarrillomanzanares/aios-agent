#!/usr/bin/env python3
"""Chat interactivo con el agente SRE."""
from agent import Agent

def main():
    agent = Agent()
    print("Agente SRE. Escribe tu consulta o 'salir'.")
    print("El agente puede ejecutar comandos, leer y escribir archivos.\n")

    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n¡Hasta luego!")
            break

        if not query:
            continue
        if query.lower() in ("salir", "exit", "quit"):
            print("¡Hasta luego!")
            break

        response = agent.run(query)
        print(f"\n{response}\n")


if __name__ == "__main__":
    main()
