import sys
sys.path.insert(0, "orchestrator")
import requests

url = "http://127.0.0.1:8080/v1/completions"

prompt = """<|user|>
Eres SRE-Copilot, asistente Linux. Responde SOLO con una de estas etiquetas: EXPLAIN, COMMAND, PLAN, ASK o DONE. Sin explicaciones extra. lista los archivos del directorio<|end|>
<|assistant|>
"""
resp = requests.post(url, json={
    "model": "local",
    "prompt": prompt,
    "temperature": 0.1,
    "max_tokens": 128,
    "top_p": 0.8,
    "repeat_penalty": 1.2,
    "echo": False,
    "stop": ["<|end|>", "<|user|>"],
}, timeout=120)
text = resp.json()["choices"][0]["text"]
print("RAW:", repr(text))

# probar con system como user
prompt2 = """<|user|>
Eres SRE-Copilot, asistente Linux. Responde SOLO con: EXPLAIN, COMMAND, PLAN, ASK o DONE.
cual es tu modelo base<|end|>
<|assistant|>
"""
resp = requests.post(url, json={
    "model": "local",
    "prompt": prompt2,
    "temperature": 0.1,
    "max_tokens": 128,
    "top_p": 0.8,
    "repeat_penalty": 1.2,
    "echo": False,
    "stop": ["<|end|>", "<|user|>"],
}, timeout=120)
text = resp.json()["choices"][0]["text"]
print("RAW2:", repr(text))
