import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/rag")
sys.path.insert(0, "/home/ccmai/sre-copilot/orchestrator")
from rag_client import RAGClient
from llm_client import LLMClient

rag = RAGClient()
llm = LLMClient()

query = "como listar servicios systemd activos"
chunks = rag.retrieve(query, n_results=3)
context = "\n\n".join([f"[{i+1}] {c['metadata'].get('source')}\n{c['text']}" for i,c in enumerate(chunks)])

system = "Eres SRE-Copilot. Responde en español breve y técnico. Genera EXPLAIN, COMMAND, ASK o DONE."
user = f"Contexto técnico:\n{context[:600]}\n\nPregunta: {query}"
messages = [{"role":"system","content":system},{"role":"user","content":user}]
resp = llm.chat(messages, temperature=0.1, max_tokens=128)
print("=== RAG CONTEXT ===")
print(context[:600])
print("\n=== LLM RESPONSE ===")
print(resp)
