import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/rag")
sys.path.insert(0, "/home/ccmai/sre-copilot/orchestrator")

import yaml
from llm_client import LLMClient
from rag_client import RAGClient
from executor import run_command

with open("/home/ccmai/sre-copilot/orchestrator/prompts.yaml", "r", encoding="utf-8") as f:
    prompts = yaml.safe_load(f)

llm = LLMClient()
rag = RAGClient()

query = "instala lynx en este servidor"
chunks = rag.retrieve(query, n_results=5)
context = "\n\n".join(
    f"[{i+1}] {c['metadata'].get('source', 'desconocido')}\n{c['text'][:1500]}"
    for i, c in enumerate(chunks)
)

system = prompts["system_prompt"]
prompt = prompts["rag_context_template"].format(context=context, question=query)
messages = [
    {"role": "system", "content": system},
    {"role": "user", "content": prompt},
]
response = llm.chat(messages, max_tokens=300, temperature=0.0)
print("=== Respuesta LLM ===")
print(response)

# Extraer línea que empiece por COMMAND: o similar
import re
m = re.search(r"(COMMAND|PLAN|EXPLAIN|ASK|DONE):\s*(.*?)(?=\n\s*(COMMAND|PLAN|EXPLAIN|ASK|DONE):|$)", response, re.DOTALL | re.IGNORECASE)
if not m:
    print("No se detectó intención ejecutable")
    sys.exit(0)

intent = m.group(1).upper().strip()
payload = m.group(2).strip()
print(f"\n=== Intención: {intent} ===")
print(f"Payload: {payload}")

if intent == "COMMAND":
    # Tomar primera línea como comando
    cmd = payload.splitlines()[0].strip().strip("`")
    print(f"\n=== Ejecutando: {cmd} ===")
    res = run_command(cmd, auto_approve_readonly=False, approved=True)
    print("success:", res["success"])
    print("returncode:", res["returncode"])
    print("stdout tail:", "\n".join(res["stdout"].strip().splitlines()[-10:]))
    print("stderr tail:", "\n".join(res["stderr"].strip().splitlines()[-10:]))
