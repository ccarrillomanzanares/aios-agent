import sys
sys.path.insert(0, "/home/ccmai/sre-copilot/rag")
import chromadb
from sentence_transformers import SentenceTransformer
import yaml

cfg_path = "/home/ccmai/sre-copilot/rag/config.yaml"
with open(cfg_path, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

client = chromadb.PersistentClient(path=cfg["db_path"])
coll = client.get_or_create_collection(name=cfg["collection_name"])

text = open("/home/ccmai/sre-copilot/data/external/sre_copilot_metadata.md", "r", encoding="utf-8").read()
model = SentenceTransformer(cfg["embedding_model"])
embedding = model.encode([text]).tolist()

# Borrar chunks antiguos del mismo source si existen
try:
    existing = coll.get(where={"source": "external/sre_copilot_metadata.md"}, include=["metadatas"])
    if existing and existing["ids"]:
        coll.delete(ids=existing["ids"])
        print("Borrados %d chunks antiguos" % len(existing["ids"]))
except Exception as e:
    print("No se pudieron borrar antiguos:", e)

coll.add(
    ids=["sre_copilot_metadata_0"],
    embeddings=embedding,
    documents=[text],
    metadatas=[{"source": "external/sre_copilot_metadata.md", "title": "sre_copilot_metadata", "category": "general", "level": "medio"}]
)
print("count final:", coll.count())
