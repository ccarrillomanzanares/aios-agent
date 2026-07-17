import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/rag")
sys.path.insert(0, "/home/ccmai/sre-copilot/orchestrator")
from rag_client import RAGClient
from llm_client import LLMClient, format_llama31, clean_response
import yaml

prompts = yaml.safe_load(open("/home/ccmai/sre-copilot/orchestrator/prompts.yaml"))
rag = RAGClient()
llm = LLMClient()

for query in ["cual es tu modelo base", "lista los archivos del directorio", "crea una script en /tmp que haga un loop con timeout 5 segundos"]:
    chunks = rag.retrieve(query, n_results=5)
    context = "\n\n".join([f"[{i+1}] {c['metadata'].get('source')}\n{c['text']}" for i,c in enumerate(chunks)])
    user_prompt = prompts["rag_context_template"].format(context=context[:2000], question=query)
    messages = [
        {"role": "system", "content": prompts["system_prompt"]},
        {"role": "user", "content": user_prompt},
    ]
    prompt = format_llama31(messages)
    print("="*40)
    print(f"QUERY: {query}")
    print(f"PROMPT LEN: {len(prompt)}")
    print("RAW RESPONSE REPR:")
    raw = llm.client.completions.create(model=llm.model, prompt=prompt, temperature=0.1, max_tokens=256, echo=False)
    print(repr(raw.choices[0].text))
    print("CLEAN:")
    print(repr(clean_response(raw.choices[0].text)))
    print("USAGE:", raw.usage)
