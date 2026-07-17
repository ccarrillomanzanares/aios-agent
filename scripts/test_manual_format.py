import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/rag")
from rag_client import RAGClient

rag = RAGClient()
query = "nginx no arranca, como diagnosticarlo"
chunks = rag.retrieve(query, n_results=5)
context = "\n\n".join([f"[{i+1}] {c['metadata'].get('source')}\n{c['text']}" for i,c in enumerate(chunks)])

system = "Eres SRE-Copilot. Responde en español breve y técnico. Responde DIRECTAMENTE, sin razonar en voz alta."
user = f"Contexto técnico:\n{context[:600]}\n\nPregunta: {query}\n\nResponde directamente usando EXPLAIN, COMMAND, ASK o DONE."

# Formato manual Llama-3.1
prompt = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n{system}<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{user}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n"

from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8080/v1", api_key="dummy")
resp = client.completions.create(model="local", prompt=prompt, max_tokens=128, temperature=0.1, stop=["<|eot_id|>"])
print("=== LLM RESPONSE ===")
print(resp.choices[0].text)
