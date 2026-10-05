"""Incrementally sync the index with the files in the docs directory.

Unchanged files (same SHA-256 as when indexed) are skipped, changed files are re-embedded,
and files that were removed from disk are removed from the index. Pass --rebuild to start over.
Runs before the API starts in Docker and Kubernetes, so restarts no longer re-embed everything.
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import List, Optional

import pipeline
from pipeline import Embedder, ExtractionError
from store import Index


def sync(index: Index, docs_dir: str, embed: Embedder) -> dict:
    summary = {"indexed": 0, "unchanged": 0, "removed": 0, "failed": 0, "chunks": 0}
    paths = pipeline.list_source_files(docs_dir)
    on_disk = {os.path.basename(p) for p in paths}

    for name in sorted(set(index.file_stats()) - on_disk):
        index.delete_file(name)
        summary["removed"] += 1
        print(f"Removed {name} (no longer in {docs_dir})")

    for path in paths:
        name = os.path.basename(path)
        with open(path, "rb") as f:
            content = f.read()
        sha = pipeline.sha256_bytes(content)
        if index.file_sha256(name) == sha:
            summary["unchanged"] += 1
            continue
        try:
            extraction = pipeline.extract_text(content, name)
            text = pipeline.require_text(extraction)
        except ExtractionError as e:
            summary["failed"] += 1
            print(f"Skipped {name}: {e}")
            continue
        chunks = pipeline.chunk_text(text)
        n = index.replace_file(name, chunks, embed(chunks), {"sha256": sha})
        summary["indexed"] += 1
        summary["chunks"] += n
        note = f" ({extraction.pages_without_text} pages had no text layer)" if extraction.pages_without_text else ""
        print(f"Indexed {name}: {n} chunks{note}")
    return summary


def main(argv: Optional[List[str]] = None, embedder: Optional[Embedder] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--docs", default=pipeline.DOCS_DIR, help="documents directory")
    parser.add_argument("--db", default=pipeline.DB_PATH, help="index file path")
    parser.add_argument("--rebuild", action="store_true", help="delete the index and re-embed every file")
    args = parser.parse_args(argv)

    os.makedirs(args.docs, exist_ok=True)
    if args.rebuild and os.path.exists(args.db):
        os.remove(os.path.realpath(args.db))  # keep a symlinked kb.db's link in place

    index = Index(args.db, dimension=pipeline.EMBED_DIM)
    paths = pipeline.list_source_files(args.docs)
    if not paths and not len(index):
        print(f"No documents in {args.docs}/ yet; add files there or upload them through the API.")
        return 0

    loaded: List[Embedder] = []

    def embed(texts: List[str]) -> List[List[float]]:
        # Load the model only if some file actually needs embedding, so a no-change restart stays fast.
        if not loaded:
            loaded.append(embedder or pipeline.load_embedder())
        return loaded[0](texts)

    s = sync(index, args.docs, embed)
    print(f"Done: {s['indexed']} indexed ({s['chunks']} chunks), {s['unchanged']} unchanged, "
          f"{s['removed']} removed, {s['failed']} failed. Index size: {len(index)} vectors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
