import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/rag")
import chromadb
from sentence_transformers import SentenceTransformer
import yaml
from pathlib import Path

with open("/home/ccmai/sre-copilot/rag/config.yaml", "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

client = chromadb.PersistentClient(path=cfg["db_path"])

try:
    client.delete_collection(name=cfg["collection_name"])
    print("Colección anterior eliminada")
except Exception as e:
    print("No había colección:", e)

coll = client.get_or_create_collection(name=cfg["collection_name"])

print("Cargando modelo de embeddings...")
model = SentenceTransformer(cfg["embedding_model"])

print("Buscando documentos...")
base = Path("/home/ccmai/sre-copilot/data/external")
docs = list(base.rglob("*.md")) + list(base.rglob("*.txt"))
print(f"Documentos encontrados: {len(docs)}")

from chunker import chunk_markdown

for i, doc_path in enumerate(docs):
    print(f"[{i+1}/{len(docs)}] {doc_path.name}...")
    text = doc_path.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        continue
    source = str(doc_path.relative_to(Path("/home/ccmai/sre-copilot/data")))
    title = doc_path.stem
    category = "general"
    lower = str(doc_path).lower()
    for cat in cfg["categories"]:
        if cat in lower:
            category = cat
            break

    chunks = chunk_markdown(
        text,
        source=source,
        title=title,
        category=category,
        level="medio",
        chunk_size=cfg["chunk_size"],
        chunk_overlap=cfg["chunk_overlap"],
    )
    if not chunks:
        continue

    ids = [f"{title}_{idx}" for idx in range(len(chunks))]
    texts = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=False).tolist()
    coll.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    print(f"  -> {len(chunks)} chunks, total índice: {coll.count()}")

print(f"Total final: {coll.count()} chunks")
