import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/rag")
sys.path.insert(0, "/home/ccmai/sre-copilot/orchestrator")

import yaml
from llm_client import LLMClient
from rag_client import RAGClient

with open("/home/ccmai/sre-copilot/orchestrator/prompts.yaml", "r", encoding="utf-8") as f:
    prompts = yaml.safe_load(f)

llm = LLMClient()
rag = RAGClient()


def query_llm(user_input: str, history: list[dict]) -> str:
    chunks = rag.retrieve(user_input, n_results=3)
    context = "\n\n".join(
        f"[{i+1}] {c['metadata'].get('source', '?')}\n{c['text'][:1200]}"
        for i, c in enumerate(chunks)
    )
    messages = [{"role": "system", "content": prompts["system_prompt"]}]

    history_lines = []
    for turn in history:
        history_lines.append(f"Usuario: {turn['user']}")
        if turn.get("assistant"):
            history_lines.append(f"Asistente: {turn['assistant']}")
    history_text = "\n".join(history_lines) if history_lines else "(sin historial)"
    last_action = history[-1].get("assistant", "(ninguna)") if history else "(ninguna)"

    prompt = prompts["rag_context_template"].format(
        context=context[:2000],
        history=history_text,
        last_action=last_action,
        question=user_input,
    )
    messages.append({"role": "user", "content": prompt})
    return llm.chat(messages, temperature=0.2, max_tokens=256)


# Simulación del caso real
turns = [
    "desinstala lynx",
    "no lynis, lynx",
    "no, con ese comando no puedes desinstalar lynx, prueba de nuevo",
]
history = []
for t in turns:
    response = query_llm(t, history)
    print(f"\n> {t}")
    print(f"< {response}")
    history.append({"user": t, "assistant": response})
