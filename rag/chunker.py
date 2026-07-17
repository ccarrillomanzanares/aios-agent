#!/usr/bin/env python3
"""Chunker robusto para documentación SRE."""
import re
from typing import List, Dict, Any


def chunk_markdown(text: str, source: str, title: str = "", category: str = "general",
                   level: str = "medio", chunk_size: int = 512,
                   chunk_overlap: int = 128) -> List[Dict[str, Any]]:
    """Divide texto en chunks con solapamiento, respetando párrafos/code blocks."""
    if not text.strip():
        return []

    # Separar por bloques: párrafos, listas, code blocks
    blocks = split_into_blocks(text)

    chunks = []
    current = []
    current_len = 0

    for block in blocks:
        block_len = len(block.split())
        if block_len > chunk_size:
            # Bloque muy largo: forzar corte por oraciones
            sub_chunks = split_long_block(block, chunk_size, chunk_overlap)
            for sub in sub_chunks:
                chunks.append(make_chunk(sub, source, title, category, level))
            continue

        if current_len + block_len > chunk_size and current:
            chunks.append(make_chunk("\n\n".join(current), source, title, category, level))
            overlap = []
            overlap_len = 0
            for b in reversed(current):
                if overlap_len + len(b.split()) > chunk_overlap:
                    break
                overlap.insert(0, b)
                overlap_len += len(b.split())
            current = overlap
            current_len = overlap_len

        current.append(block)
        current_len += block_len

    if current:
        chunks.append(make_chunk("\n\n".join(current), source, title, category, level))

    return chunks


def split_into_blocks(text: str) -> List[str]:
    """Divide el texto en bloques lógicos (párrafos, listas, code blocks)."""
    blocks = []
    lines = text.splitlines()
    current = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            in_code = not in_code
            current.append(line)
            if not in_code:
                blocks.append("\n".join(current).strip())
                current = []
            continue

        if in_code:
            current.append(line)
            continue

        if line.strip() == "":
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue

        current.append(line)

    if current:
        blocks.append("\n".join(current).strip())

    return [b for b in blocks if b]


def split_long_block(block: str, chunk_size: int, overlap: int) -> List[str]:
    """Corta bloques largos por oraciones."""
    sentences = re.split(r'(?<=[.!?])\s+', block)
    chunks = []
    current = []
    current_len = 0

    for sent in sentences:
        sent_len = len(sent.split())
        if current_len + sent_len > chunk_size and current:
            chunks.append(" ".join(current))
            # overlap
            overlap_sents = []
            overlap_len = 0
            for s in reversed(current):
                if overlap_len + len(s.split()) > overlap:
                    break
                overlap_sents.insert(0, s)
                overlap_len += len(s.split())
            current = overlap_sents
            current_len = overlap_len
        current.append(sent)
        current_len += sent_len

    if current:
        chunks.append(" ".join(current))
    return chunks


def make_chunk(text: str, source: str, title: str, category: str, level: str) -> Dict[str, Any]:
    return {
        "text": text,
        "metadata": {
            "source": source,
            "title": title,
            "category": category,
            "level": level,
        },
    }
