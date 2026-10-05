import sys

import pipeline
from store import Index

def main():
    if len(sys.argv) < 2:
        print("Usage: python cli_search.py \"your question\"")
        sys.exit(1)

    q = sys.argv[1]
    embed = pipeline.load_embedder()
    index = Index(pipeline.DB_PATH, dimension=pipeline.EMBED_DIM)
    results = index.search(embed([q])[0], 5)

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
