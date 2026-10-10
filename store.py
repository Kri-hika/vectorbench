"""Vector stores behind one interface, so the API, ingester and benchmarks can run on either backend.

Two implementations:
  * VectorLiteStore (this file): embedded, a single VectorLiteDB file held in memory by one process.
  * PgVectorStore (store_pg.py): Postgres + pgvector, shared by any number of API replicas.

Pick one with VB_STORE=vectorlite (default) or VB_STORE=pgvector; see open_store().
Both return search hits as {"id": "<file>::<index>", "similarity": 1/(1+cosine distance),
"metadata": {"file", "index", "chunk", "file_type", "sha256"}} so callers cannot tell them apart.
"""
from __future__ import annotations

import copy
import os
import struct
import tempfile
import threading
from typing import Any, Callable, Dict, List, Optional, Protocol, Sequence

from vectorlitedb import VectorLiteDB


class VectorStore(Protocol):
    name: str
    # True when the store keeps each uploaded file's bytes itself (pgvector). Then the API stays
    # stateless and the database, not a docs directory, is the source of truth.
    stores_sources: bool

    def __len__(self) -> int: ...
    def search(self, vector: Sequence[float], k: int, file: Optional[str] = None) -> List[Dict[str, Any]]: ...
    def file_stats(self) -> Dict[str, Dict[str, Any]]: ...
    def file_sha256(self, filename: str) -> Optional[str]: ...
    def replace_file(self, filename: str, chunks: Sequence[str], vectors: Sequence[Sequence[float]],
                     sha256: Optional[str] = None, source: Optional[bytes] = None) -> int: ...
    def delete_file(self, filename: str) -> int: ...
    def close(self) -> None: ...


def file_type_of(filename: str) -> str:
    return os.path.splitext(filename)[1].lstrip(".").lower()


def open_store(kind: Optional[str] = None, *, db_path: Optional[str] = None,
               dimension: int = 384) -> VectorStore:
    """Open the store named by `kind` or VB_STORE. Postgres settings come from VB_PG_* variables."""
    kind = (kind or os.getenv("VB_STORE", "vectorlite")).lower()
    if kind == "vectorlite":
        return VectorLiteStore(db_path or os.getenv("VB_DB_PATH", "kb.db"), dimension=dimension)
    if kind == "pgvector":
        from store_pg import PgVectorStore  # optional dependency, imported only when selected
        return PgVectorStore.from_env(dimension=dimension)
    raise ValueError(f"Unknown VB_STORE {kind!r}; expected 'vectorlite' or 'pgvector'")


class CorruptIndexError(RuntimeError):
    """The index file exists but cannot be read (truncated, partially written, or not an index)."""


class VectorLiteStore:
    """Thread-safe, per-file index on top of VectorLiteDB.

    VectorLiteDB 0.1.0 has three properties this class works around:
      1. insert()/delete() rewrite the whole database file on every call, so inserting N chunks
         one at a time costs O(N^2) disk writes. Commits here change the in-memory maps and save once.
      2. Its save truncates the file before writing, so a crash mid-save leaves a corrupt file.
         Commits here save to a temp file next to the real one and swap it in with os.replace().
      3. It has no locking. Commits here build new maps and swap them in (copy-on-write), and one lock
         serializes writers (two unsynchronized commits would overwrite each other's temp file) and keeps
         searches from seeing new vectors paired with old metadata mid-swap.

    (1) and (2) use VectorLiteDB's `vectors`/`metadata` maps and `_save()` directly, which is why
    requirements.txt pins vectorlitedb==0.1.0. Re-check this class before upgrading it.

    Each process keeps the whole index in memory and writes the file from that copy, so exactly one
    process may own a given file. That is the limit the pgvector backend exists to remove.
    """

    name = "vectorlite"
    stores_sources = False

    def __init__(self, path: str, dimension: int, distance_metric: str = "cosine"):
        self.path = path
        self._lock = threading.RLock()
        try:
            self._db = VectorLiteDB(path, dimension=dimension, distance_metric=distance_metric)
        except (ValueError, KeyError, struct.error) as e:  # JSONDecodeError is a ValueError
            # Saves here are atomic, so this means a file written by an older version, a crash in
            # one, or the wrong file. The originals in the docs directory can rebuild it.
            raise CorruptIndexError(
                f"Index file {path!r} is unreadable ({type(e).__name__}: {e}). Restore it from a "
                "backup, or re-embed the docs directory with: python ingest.py --rebuild") from e

    def __len__(self) -> int:
        with self._lock:
            return len(self._db)

    def close(self) -> None:
        """Nothing to release: every commit is already on disk."""

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
                     sha256: Optional[str] = None, source: Optional[bytes] = None) -> int:
        """Atomically swap every chunk of `filename` for the given chunks. Returns the new chunk count.

        `source` is ignored: in this backend the original file lives in the docs directory.
        """
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be the same length")
        dim = self._db.dimension
        for v in vectors:
            if len(v) != dim:
                raise ValueError(f"Vector dimension mismatch: expected {dim}, got {len(v)}")
        file_type = file_type_of(filename)

        def mutate(vecs: Dict[str, Any], metas: Dict[str, Any]) -> None:
            for vid in [i for i, m in metas.items() if m and m.get("file") == filename]:
                vecs.pop(vid, None)
                metas.pop(vid, None)
            for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
                vid = f"{filename}::{idx}"
                vecs[vid] = list(vec)
                metas[vid] = {"file": filename, "index": idx, "chunk": chunk,
                              "file_type": file_type, "sha256": sha256}

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
