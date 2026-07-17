import sys
sys.path.insert(0, "orchestrator")
from llm_client import LLMClient
import requests

llm = LLMClient()
print("health:", llm.health())

messages = [
    {"role": "system", "content": "Eres SRE-Copilot, asistente Linux. Responde con EXPLAIN, COMMAND, PLAN, ASK o DONE."},
    {"role": "user", "content": "cual es tu modelo base"},
]
prompt = llm.format_prompt(messages)
print("--- PROMPT ---")
print(prompt)
print("--- RAW ---")
resp = requests.post(llm.completions_url, json={
    "model": "local",
    "prompt": prompt,
    "temperature": 0.2,
    "max_tokens": 256,
    "top_p": 0.9,
    "echo": False,
    "stop": ["<|end|>", "<|user|>", "<|eot_id|>"],
}, timeout=120)
print(resp.json()["choices"][0]["text"])
print("--- CLEAN ---")
print(llm.chat(messages))
