import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/rag")
from rag_client import RAGClient
rag = RAGClient()
for c in rag.retrieve("cual es tu modelo base", n_results=5):
    print(c["metadata"].get("source"), c["distance"])
