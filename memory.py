"""Lightweight procedural memory for the SRE agent.

Learns solutions from experience without modifying the LLM.
Based on the ProcMEM pattern (arXiv 2602.01869) and Claude Agent Skills.
"""
import json
import time
from pathlib import Path

MEMORY_FILE = "skills_memory.json"
SIMILARITY_THRESHOLD = 0.75


class ProceduralMemory:
    """Procedural cache: query → solution, with duplicate removal."""

    def __init__(self, path: str = MEMORY_FILE):
        self.path = Path(path)
        self.skills: list[dict] = []
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                self.skills = json.loads(self.path.read_text())
            except (json.JSONDecodeError, Exception):
                self.skills = []

    def _save(self):
        self.path.write_text(json.dumps(self.skills, ensure_ascii=False, indent=2))

    def _simple_sim(self, a: str, b: str) -> float:
        """Basic similarity: word intersection / union."""
        sa, sb = set(a.lower().split()), set(b.lower().split())
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    def _normalize_key(self, query: str, llm_call) -> str:
        """Use the LLM to generate a canonical key for the query."""
        prompt = f"Convierte esta consulta en una clave técnica de 2-5 palabras, solo la clave, sin explicación:\n\n{query}"
        try:
            key = llm_call(prompt).strip().lower()
            return key if key else query.lower()
        except Exception:
            return query.lower()

    def find(self, query: str, llm_call) -> str | None:
        """Search for a cached solution. Returns None if not found."""
        key = self._normalize_key(query, llm_call)
        # Exact search
        for s in self.skills:
            if s.get("key") == key:
                s["hits"] = s.get("hits", 0) + 1
                s["last_used"] = time.time()
                self._save()
                return s["solution"]
        # Similarity search
        for s in self.skills:
            if self._simple_sim(key, s.get("key", "")) > SIMILARITY_THRESHOLD:
                s["hits"] = s.get("hits", 0) + 1
                s["last_used"] = time.time()
                self._save()
                return s["solution"]
        return None

    def store(self, query: str, solution: str, llm_call):
        """Store a new solution."""
        try:
            key = self._normalize_key(query, llm_call)
        except Exception:
            key = query.lower()
        # Avoid duplicates
        for s in self.skills:
            if s.get("key") == key:
                s["solution"] = solution
                s["hits"] = s.get("hits", 0) + 1
                s["last_used"] = time.time()
                self._save()
                return
        self.skills.append({
            "key": key,
            "query": query,
            "solution": solution,
            "hits": 1,
            "created": time.time(),
            "last_used": time.time(),
        })
        # Limit to 200 entries, drop least used
        if len(self.skills) > 200:
            self.skills.sort(key=lambda s: s.get("hits", 0))
            self.skills = self.skills[-200:]
        self._save()

    def stats(self) -> dict:
        return {"total": len(self.skills), "top5": sorted(self.skills, key=lambda s: s.get("hits", 0), reverse=True)[:5]}
