import sys
from pathlib import Path

sys.path.insert(0, "/home/ccmai/sre-copilot/rag")
sys.path.insert(0, "/home/ccmai/sre-copilot/orchestrator")

import yaml
from llm_client import LLMClient
from rag_client import RAGClient
from main import load_prompts, format_context, parse_llm_output, build_messages_with_history

prompts = load_prompts()
rag = RAGClient()
llm = LLMClient()

queries = [
    "como configurar un chroot SFTP",
    "como crear un snapshot ZFS",
    "como configurar WireGuard en un servidor",
]

for query in queries:
    print("=" * 60)
    print(f"Pregunta: {query}")
    print("=" * 60)

    chunks = rag.retrieve(query, n_results=5)
    print("\n[Contexto RAG]")
    for i, c in enumerate(chunks, 1):
        print(f"{i}. {c['metadata'].get('source')} (dist={c.get('distance', '?'):.3f})")
        preview = c["text"].replace("\n", " ")[:120]
        print(f"   {preview}...")

    context = format_context(chunks)
    messages = build_messages_with_history(prompts, prompts["system_prompt"], query, context, [])
    response = llm.chat(messages, temperature=0.2, max_tokens=512)

    intent, payload = parse_llm_output(response)
    print(f"\n[Respuesta LLM]")
    print(f"Intención: {intent}")
    print(f"Payload:\n{payload}")
    print()
