import sys
from sentence_transformers import SentenceTransformer
from vectorlitedb import VectorLiteDB

DB_PATH = "kb.db"
DIM = 384

def main():
    if len(sys.argv) < 2:
        print("Usage: python cli_search.py \"your question\"")
        sys.exit(1)

    q = sys.argv[1]
    model = SentenceTransformer("all-MiniLM-L6-v2")
    db = VectorLiteDB(DB_PATH, dimension=DIM)

    q_vec = model.encode(q).tolist()
    results = db.search(query=q_vec, top_k=5)

    print("\nTop matches:\n------------")
    for i, r in enumerate(results, 1):
        meta = r["metadata"]
        preview = (meta.get("chunk", "") or "").strip().replace("\n", " ")
        if len(preview) > 160:
            preview = preview[:157] + "..."
        print(f"{i}. {r['id']}  (sim={r['similarity']:.4f})  file={meta.get('file')}")
        print(f"   {preview}\n")

if __name__ == "__main__":
    main()
