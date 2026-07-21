#!/usr/bin/env python3
"""Interactive chat with the SRE agent.
The session is automatically saved on exit and resumed on startup."""
import json
from pathlib import Path

from agent import Agent
from tools import execute_tool


def handle_slash(agent: Agent, query: str) -> bool:
    """Process slash commands. Returns True if the command was consumed."""
    cmd = query.strip()
    lowered = cmd.lower()

    if lowered == "/retry":
        # Remove the last exchange from history (user + assistant/tool)
        if len(agent.messages) <= 1:
            print("  [No exchanges to retry]")
        else:
            removed = []
            # Delete in reverse order until a full exchange is consumed
            while len(agent.messages) > 1:
                last = agent.messages.pop()
                removed.append(last["role"])
                if last["role"] == "user":
                    break
            print(f"  [Last exchange removed ({', '.join(removed)})]")
        return True

    if lowered == "/save":
        agent._save_session()
        from agent import SESSION_FILE
        print(f"  [Session saved to {SESSION_FILE}]")
        return True

    if lowered == "/clear":
        system = agent.messages[0] if agent.messages else {"role": "system", "content": ""}
        agent.messages = [system]
        print("  [History cleared; system prompt preserved]")
        return True

    if lowered == "/stats":
        total_msgs = len(agent.messages)
        memory_count = len(agent.memory.skills) if agent.memory else 0
        from agent import SESSION_FILE
        session_file = Path(SESSION_FILE)
        session_size = session_file.stat().st_size if session_file.exists() else 0
        print(f"  [Stats] messages: {total_msgs}, skills in memory: {memory_count}, session.json: {session_size} bytes")
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
            print(f"  [Error executing git_operation: {e}]")
        return True

    return False


def main():
    agent = Agent()
    print("SRE Agent. Type your query or 'exit'.")
    print("Commands: /retry /save /clear /stats /git [status|diff|...]")
    print("The agent can run commands, read and write files.\n")

    while True:
        try:
            query = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            agent._save_session()
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() in ("salir", "exit", "quit"):
            agent._save_session()
            print("Goodbye!")
            break

        # Process slash commands before sending to the agent
        if query.startswith("/") and handle_slash(agent, query):
            continue

        response = agent.run(query)
        print(f"\n{response}\n")


if __name__ == "__main__":
    main()
