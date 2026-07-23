"""Memoria procedural ligera para el agente SRE.

Aprende soluciones de la experiencia sin modificar el LLM.
Basado en el patrón ProcMEM (arXiv 2602.01869) y Claude Agent Skills.
"""
import json
import os
import time
from pathlib import Path

MEMORY_FILE = "skills_memory.json"
SIMILARITY_THRESHOLD = 0.75


class ProceduralMemory:
    """Caché procedural: query → solución, con eliminación de duplicados."""

    def __init__(self, path: str = None):
        self.mode = os.environ.get("AIOS_MODE", "local")
        self.path = Path(path or f"skills_memory_{self.mode}.json")
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
        """Similitud básica: intersección de palabras / unión."""
        sa, sb = set(a.lower().split()), set(b.lower().split())
        if not sa or not sb:
            return 0.0
        return len(sa & sb) / len(sa | sb)

    def _normalize_key(self, query: str, llm_call) -> str:
        """Usa el LLM para generar clave canónica de la consulta."""
        prompt = f"Convierte esta consulta en una clave técnica de 2-5 palabras, solo la clave, sin explicación:\n\n{query}"
        try:
            key = llm_call(prompt).strip().lower()
            return key if key else query.lower()
        except Exception:
            return query.lower()

    def find(self, query: str, llm_call) -> str | None:
        """Busca una solución cacheada. Devuelve None si no hay."""
        key = self._normalize_key(query, llm_call)
        # Búsqueda exacta
        for s in self.skills:
            if s.get("key") == key:
                s["hits"] = s.get("hits", 0) + 1
                s["last_used"] = time.time()
                self._save()
                return s["solution"]
        # Búsqueda por similitud
        for s in self.skills:
            if self._simple_sim(key, s.get("key", "")) > SIMILARITY_THRESHOLD:
                s["hits"] = s.get("hits", 0) + 1
                s["last_used"] = time.time()
                self._save()
                return s["solution"]
        return None

    def store(self, query: str, solution: str, llm_call):
        """Guarda una nueva solución."""
        try:
            key = self._normalize_key(query, llm_call)
        except Exception:
            key = query.lower()
        # Evitar duplicados
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
        # Limitar a 200 entradas, eliminar las menos usadas
        if len(self.skills) > 200:
            self.skills.sort(key=lambda s: s.get("hits", 0))
            self.skills = self.skills[-200:]
        self._save()

    def stats(self) -> dict:
        return {"total": len(self.skills), "top5": sorted(self.skills, key=lambda s: s.get("hits", 0), reverse=True)[:5]}
