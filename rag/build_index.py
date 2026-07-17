#!/usr/bin/env python3
"""Construye el índice vectorial ChromaDB para el RAG SRE."""
import argparse
import os
import sys
from pathlib import Path

import chromadb
import yaml
from sentence_transformers import SentenceTransformer

sys.path.insert(0, str(Path(__file__).parent))
from chunker import chunk_markdown


def load_config():
    cfg_path = Path(__file__).parent / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def discover_documents(input_dir: Path):
    docs = []
    for ext in ("*.md", "*.txt"):
        docs.extend(input_dir.rglob(ext))
    return docs


def load_doc(path: Path) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def guess_category(path: Path, categories: list) -> str:
    lower = str(path).lower()
    for cat in categories:
        if cat in lower:
            return cat
    return "general"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="/home/ccmai/sre-copilot/data")
    parser.add_argument("--db", default=None)
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--reset", action="store_true", help="Reconstruye la colección desde cero")
    args = parser.parse_args()

    cfg = load_config()
    db_path = args.db or cfg["db_path"]
    input_dir = Path(args.input)

    client = chromadb.PersistentClient(path=db_path)

    if args.reset:
        try:
            client.delete_collection(name=cfg["collection_name"])
            print(f"Colección anterior '{cfg['collection_name']}' eliminada.")
        except Exception:
            pass

    collection = client.get_or_create_collection(name=cfg["collection_name"])

    if args.stats:
        print(f"Documentos indexados: {collection.count()}")
        return

    model = SentenceTransformer(cfg["embedding_model"])

    docs = discover_documents(input_dir)
    print(f"Documentos encontrados: {len(docs)}")

    for doc_path in docs:
        text = load_doc(doc_path)
        if not text.strip():
            continue
        source = str(doc_path.relative_to(input_dir))
        title = doc_path.stem
        category = guess_category(doc_path, cfg["categories"])
        level = "medio"
        chunks = chunk_markdown(
            text,
            source=source,
            title=title,
            category=category,
            level=level,
            chunk_size=cfg["chunk_size"],
            chunk_overlap=cfg["chunk_overlap"],
        )
        if not chunks:
            continue

        ids = [f"{title}_{i}" for i in range(len(chunks))]
        texts = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]
        embeddings = model.encode(texts, show_progress_bar=False).tolist()

        collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        print(f"  {source}: {len(chunks)} chunks")

    print(f"Total chunks indexados: {collection.count()}")


if __name__ == "__main__":
    main()
