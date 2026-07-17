import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/rag")
sys.path.insert(0, "/home/ccmai/sre-copilot/orchestrator")
from rag_client import RAGClient
from llm_client import LLMClient
import yaml

with open("/home/ccmai/sre-copilot/orchestrator/prompts.yaml") as f:
    prompts = yaml.safe_load(f)

rag = RAGClient()
llm = LLMClient()
query = "lista los archivos del directorio"
chunks = rag.retrieve(query, n_results=3)
context = "\n\n".join([f"[{i+1}] {c['metadata'].get('source')}\n{c['text']}" for i,c in enumerate(chunks)])
print("=== CONTEXT ===")
print(context[:1000])
print("\n=== PROMPT ===")
user = prompts["rag_context_template"].format(context=context[:1500], question=query)
print(user[:500])
print("\n=== LLM RAW ===")
messages = [{"role": "system", "content": prompts["system_prompt"]}, {"role": "user", "content": user}]
resp = llm.chat(messages, temperature=0.1, max_tokens=128)
print(repr(resp))
print("\n=== CLEAN ===")
print(resp)
