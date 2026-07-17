#!/usr/bin/env python3
"""Cliente OpenAI-compatible para llama-server.

Soporta varios formatos de prompt según el modelo:
  - llama3 (Meta-Llama-3.x-Instruct)
  - phi4 (Microsoft Phi-4-mini-instruct)
"""
import json
import os
import re
from pathlib import Path

import requests


BASE_URL = os.environ.get("SRE_LLM_URL", "http://127.0.0.1:8080")
COMPLETIONS_URL = f"{BASE_URL}/v1/completions"
MODELS_URL = f"{BASE_URL}/v1/models"

# Tokens especiales Llama-3
BOS = "<|begin_of_text|>"
EOT = "<|eot_id|>"
START_H = "<|start_header_id|>"
END_H = "<|end_header_id|>"

# Tokens Phi-4
PHI4_USER = "<|user|>"
PHI4_ASSISTANT = "<|assistant|>"
PHI4_SYSTEM = "<|system|>"
PHI4_END = "<|end|>"


class LLMClient:
    def __init__(self, base_url: str = None, model_format: str = None):
        self.base_url = base_url or BASE_URL
        self.completions_url = f"{self.base_url}/v1/completions"
        self.models_url = f"{self.base_url}/v1/models"
        self.model_format = model_format or self._detect_model_format()

    def _detect_model_format(self) -> str:
        try:
            r = requests.get(self.models_url, timeout=10)
            r.raise_for_status()
            model_id = r.json()["data"][0].get("id", "")
            if "phi" in model_id.lower():
                return "phi4"
            return "llama3"
        except Exception:
            return "llama3"

    def _detect_format_from_messages(self, messages: list[dict]) -> str:
        text = "\n".join(m.get("content", "") for m in messages)
        if PHI4_USER in text or PHI4_ASSISTANT in text or PHI4_SYSTEM in text:
            return "phi4"
        return "llama3"

    def _format_llama3(self, messages: list[dict]) -> str:
        parts = []
        for m in messages:
            role = m["role"]
            content = m.get("content", "")
            parts.append(f"{START_H}{role}{END_H}\n{content}{EOT}")
        parts.append(f"{START_H}assistant{END_H}\n")
        return "".join(parts)

    def _format_phi4(self, messages: list[dict]) -> str:
        parts = []
        for m in messages:
            role = m["role"]
            content = m.get("content", "")
            if role == "system":
                parts.append(f"{PHI4_SYSTEM}\n{content}{PHI4_END}")
            elif role == "user":
                parts.append(f"{PHI4_USER}\n{content}{PHI4_END}")
            elif role == "assistant":
                parts.append(f"{PHI4_ASSISTANT}\n{content}{PHI4_END}")
        parts.append(f"{PHI4_ASSISTANT}\n")
        return "\n".join(parts)

    def format_prompt(self, messages: list[dict]) -> str:
        fmt = self._detect_format_from_messages(messages)
        if fmt == "phi4" or self.model_format == "phi4":
            return self._format_phi4(messages)
        return self._format_llama3(messages)

    def _truncate_on_tokens(self, text: str) -> str:
        tokens = [PHI4_USER, PHI4_ASSISTANT, PHI4_SYSTEM, PHI4_END, EOT, BOS, START_H]
        earliest = len(text)
        for tok in tokens:
            idx = text.find(tok)
            if idx != -1 and idx < earliest:
                earliest = idx
        if earliest < len(text):
            text = text[:earliest].strip()
        return text

    def clean_response(self, text: str, prompt_format: str = "llama3") -> str:
        text = text.strip()
        if not text:
            return ""

        marker_re = re.compile(
            r"(?:^|\n|\s)(EXPLAIN|COMMAND|PLAN|ASK|DONE)\s*:?\s*",
            re.IGNORECASE,
        )
        match = marker_re.search(text)
        if match:
            intent = match.group(1).upper()
            start = match.end()
            rest = text[start:].strip()
            rest = self._truncate_on_tokens(rest)
            if intent == "COMMAND":
                code_match = re.search(r"```(?:bash)?\n(.*?)\n```", rest, re.DOTALL)
                if code_match:
                    return f"COMMAND: {code_match.group(1).strip()}"
                first_line = rest.splitlines()[0].strip().strip("`")
                if first_line:
                    return f"COMMAND: {first_line}"
                return f"COMMAND: {rest}"
            elif intent == "PLAN":
                return f"PLAN: {rest}"
            elif intent == "ASK":
                return f"ASK: {rest}"
            elif intent == "DONE":
                return "DONE"
            else:
                return f"EXPLAIN: {rest}"

        text = self._truncate_on_tokens(text)
        return text

    def chat(self, messages: list[dict], temperature: float = 0.2,
             max_tokens: int = 256, top_p: float = 0.9) -> str:
        fmt = self._detect_format_from_messages(messages)
        if fmt == "phi4" or self.model_format == "phi4":
            fmt = "phi4"
        prompt = self.format_prompt(messages)
        payload = {
            "model": "local",
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "echo": False,
            "stop": [PHI4_END, PHI4_USER, EOT, "<|eot_id|>"],
        }
        resp = requests.post(self.completions_url, json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["text"]
        return self.clean_response(text, fmt)

    def health(self) -> dict:
        r = requests.get(f"{self.base_url}/health", timeout=10)
        r.raise_for_status()
        return r.json()


if __name__ == "__main__":
    import sys

    llm = LLMClient()
    if len(sys.argv) > 1 and sys.argv[1] == "--models":
        r = requests.get(MODELS_URL, timeout=10)
        print(json.dumps(r.json(), indent=2))
    else:
        messages = [
            {"role": "system", "content": "Eres SRE-Copilot, asistente Linux."},
            {"role": "user", "content": "cual es tu modelo base"},
        ]
        print(llm.chat(messages))
