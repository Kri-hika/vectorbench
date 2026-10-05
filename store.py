"""Thread-safe, per-file index on top of VectorLiteDB.

VectorLiteDB 0.1.0 has three properties this module works around:
  1. insert()/delete() rewrite the whole database file on every call, so inserting N chunks
     one at a time costs O(N^2) disk writes. Commits here change the in-memory maps and save once.
  2. Its save truncates the file before writing, so a crash mid-save leaves a corrupt file.
     Commits here save to a temp file next to the real one and swap it in with os.replace().
  3. It has no locking. Commits here build new maps and swap them in (copy-on-write), and one lock
     serializes writers (two unsynchronized commits would overwrite each other's temp file) and keeps
     searches from seeing new vectors paired with old metadata mid-swap.

(1) and (2) use VectorLiteDB's `vectors`/`metadata` maps and `_save()` directly, which is why
requirements.txt pins vectorlitedb==0.1.0. Re-check this module before upgrading it.
"""
from __future__ import annotations

import copy
import os
import tempfile
import threading
from typing import Any, Callable, Dict, List, Optional, Sequence

from vectorlitedb import VectorLiteDB


class Index:
    def __init__(self, path: str, dimension: int, distance_metric: str = "cosine"):
        self.path = path
        self._lock = threading.RLock()
        self._db = VectorLiteDB(path, dimension=dimension, distance_metric=distance_metric)

    def __len__(self) -> int:
        with self._lock:
            return len(self._db)

    # --- reads ---

    def search(self, vector: Sequence[float], k: int,
               file: Optional[str] = None) -> List[Dict[str, Any]]:
        meta_filter: Optional[Callable[[Dict[str, Any]], bool]] = None
        if file:
            meta_filter = lambda m: m.get("file") == file  # noqa: E731
        with self._lock:
            return self._db.search(query=list(vector), top_k=k, filter=meta_filter)

    def file_stats(self) -> Dict[str, Dict[str, Any]]:
        """{filename: {"chunks": n, "sha256": hash or None}} straight from metadata, no search."""
        stats: Dict[str, Dict[str, Any]] = {}
        with self._lock:
            for meta in self._db.metadata.values():
                if not meta or not meta.get("file"):
                    continue
                entry = stats.setdefault(meta["file"], {"chunks": 0, "sha256": meta.get("sha256")})
                entry["chunks"] += 1
        return stats

    def file_sha256(self, filename: str) -> Optional[str]:
        return self.file_stats().get(filename, {}).get("sha256")

    # --- writes ---

    def replace_file(self, filename: str, chunks: Sequence[str], vectors: Sequence[Sequence[float]],
                     extra_meta: Optional[Dict[str, Any]] = None) -> int:
        """Atomically swap every chunk of `filename` for the given chunks. Returns the new chunk count."""
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be the same length")
        dim = self._db.dimension
        for v in vectors:
            if len(v) != dim:
                raise ValueError(f"Vector dimension mismatch: expected {dim}, got {len(v)}")

        def mutate(vecs: Dict[str, Any], metas: Dict[str, Any]) -> None:
            for vid in [i for i, m in metas.items() if m and m.get("file") == filename]:
                vecs.pop(vid, None)
                metas.pop(vid, None)
            for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
                vid = f"{filename}::{idx}"
                vecs[vid] = list(vec)
                metas[vid] = {"file": filename, "index": idx, "chunk": chunk,
                              "file_type": os.path.splitext(filename)[1].lstrip(".").lower(),
                              **(extra_meta or {})}

        self._commit(mutate)
        return len(chunks)

    def delete_file(self, filename: str) -> int:
        """Remove every chunk of `filename`. Returns how many were removed."""
        removed = 0

        def mutate(vecs: Dict[str, Any], metas: Dict[str, Any]) -> None:
            nonlocal removed
            for vid in [i for i, m in metas.items() if m and m.get("file") == filename]:
                vecs.pop(vid, None)
                metas.pop(vid, None)
                removed += 1

        self._commit(mutate)
        return removed

    def _commit(self, mutate: Callable[[Dict[str, Any], Dict[str, Any]], None]) -> None:
        """Apply `mutate` to copies of the maps, persist atomically, then publish them.

        If anything fails, the in-memory index and the file on disk both stay as they were.
        """
        with self._lock:
            db = self._db
            old_vecs, old_metas = db.vectors, db.metadata
            new_vecs, new_metas = dict(old_vecs), copy.copy(old_metas)
            mutate(new_vecs, new_metas)

            # Write through a symlinked kb.db (used to keep the DB out of iCloud) instead of replacing the link.
            real_path = os.path.realpath(self.path)
            fd, tmp_path = tempfile.mkstemp(prefix=".vldb-", suffix=".tmp",
                                            dir=os.path.dirname(real_path) or ".")
            os.close(fd)
            db.vectors, db.metadata = new_vecs, new_metas
            try:
                db.db_path = tmp_path
                db._save()
                os.replace(tmp_path, real_path)
            except BaseException:
                db.vectors, db.metadata = old_vecs, old_metas
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise
            finally:
                db.db_path = self.path
