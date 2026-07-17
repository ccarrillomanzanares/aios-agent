#!/usr/bin/env python3
"""Cliente de RAG para recuperar contexto técnico SRE."""
from pathlib import Path

import chromadb
import yaml
from sentence_transformers import SentenceTransformer


class RAGClient:
    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        with open(config_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.client = chromadb.PersistentClient(path=self.cfg["db_path"])
        self.collection = self.client.get_or_create_collection(
            name=self.cfg["collection_name"]
        )
        self.model = SentenceTransformer(self.cfg["embedding_model"])

    def _keyword_boost(self, query: str, chunks: list, n_results: int) -> list:
        """Re-ordena ligeramente los resultados si contienen palabras clave de la query."""
        q_lower = query.lower()
        q_tokens = set(q_lower.split())

        identity_keywords = {"modelo", "base", "identidad", "quién", "eres", "asistente"}
        is_identity_query = bool(identity_keywords & q_tokens) or "modelo base" in q_lower

        scored = []
        for c in chunks:
            text_lower = c["text"].lower()
            meta_source = c["metadata"].get("source", "").lower()
            matches = sum(1 for t in q_tokens if t in text_lower or t in meta_source)

            # Bonus fuerte para el documento de metadatos del sistema
            if "sre_copilot_metadata" in meta_source:
                if is_identity_query:
                    matches += 10
                else:
                    matches += 1

            scored.append((matches, c))
        scored.sort(key=lambda x: (x[0], -x[1]["distance"]), reverse=True)
        return [c for _, c in scored[:n_results]]

    def retrieve(self, query: str, n_results: int = 5):
        embedding = self.model.encode([query]).tolist()
        results = self.collection.query(
            query_embeddings=embedding,
            n_results=n_results * 2,
            include=["documents", "metadatas", "distances"],
        )
        chunks = []
        for i in range(len(results["documents"][0])):
            chunks.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            })
        return self._keyword_boost(query, chunks, n_results)


if __name__ == "__main__":
    import sys

    query = sys.argv[1] if len(sys.argv) > 1 else "nginx no arranca"
    rag = RAGClient()
    for chunk in rag.retrieve(query):
        print(f"--- {chunk['metadata'].get('source')} ---")
        print(chunk["text"][:500])
        print()
