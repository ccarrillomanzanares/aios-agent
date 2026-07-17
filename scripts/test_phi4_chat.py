import sys
sys.path.insert(0, "orchestrator")
import requests

url = "http://127.0.0.1:8080/v1/chat/completions"
messages = [
    {"role": "system", "content": "Eres SRE-Copilot, asistente Linux. Responde con EXPLAIN, COMMAND, PLAN, ASK o DONE."},
    {"role": "user", "content": "cual es tu modelo base"},
]
resp = requests.post(url, json={
    "model": "local",
    "messages": messages,
    "temperature": 0.2,
    "max_tokens": 256,
    "top_p": 0.9,
}, timeout=120)
print(resp.json()["choices"][0]["message"]["content"])

messages = [
    {"role": "system", "content": "Eres SRE-Copilot, asistente Linux. Responde con EXPLAIN, COMMAND, PLAN, ASK o DONE."},
    {"role": "user", "content": "lista los archivos del directorio"},
]
resp = requests.post(url, json={
    "model": "local",
    "messages": messages,
    "temperature": 0.2,
    "max_tokens": 256,
    "top_p": 0.9,
}, timeout=120)
print(resp.json()["choices"][0]["message"]["content"])
