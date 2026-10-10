"""Postgres + pgvector implementation of the VectorStore interface (see store.py).

What it changes relative to the embedded store:
  * Replacing a file's chunks is one transaction, not a hand-built temp-file swap.
  * Any number of API processes can read and write at once, so the API can run as several replicas.
  * The original file bytes are stored next to their chunks, so no replica needs a local docs directory.
  * Search uses an HNSW index (approximate) by default. VB_PG_SEARCH=exact forces a full scan on the
    same data, which is how the benchmark measures how much recall the index gives up.

Settings (environment): VB_PG_DSN, VB_PG_SCHEMA (default public), VB_PG_SEARCH (hnsw|exact),
VB_PG_EF_SEARCH (HNSW candidate list size, pgvector default 40), VB_PG_POOL_MAX (default 8).
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Sequence

import numpy as np
import psycopg
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg_pool import ConnectionPool

from store import file_type_of

_SCHEMA_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
_SCHEMA_LOCK_KEY = 0x7EC7_0BE7  # advisory lock id: replicas starting together create the schema once


class PgVectorStore:
    name = "pgvector"
    stores_sources = True

    def __init__(self, dsn: str, dimension: int = 384, *, schema: str = "public",
                 search_mode: str = "hnsw", ef_search: int = 40, pool_max: int = 8):
        if not _SCHEMA_NAME.match(schema):
            raise ValueError(f"Invalid schema name {schema!r}")
        if search_mode not in ("hnsw", "exact"):
            raise ValueError("search_mode must be 'hnsw' or 'exact'")
        self.dsn, self.dimension, self.schema = dsn, dimension, schema
        self.search_mode, self.ef_search = search_mode, ef_search
        self._init_schema()
        self._pool = ConnectionPool(dsn, min_size=1, max_size=pool_max, configure=self._configure,
                                    open=True, name="vectorbench")

    @classmethod
    def from_env(cls, dimension: int = 384) -> "PgVectorStore":
        dsn = os.getenv("VB_PG_DSN")
        if not dsn:
            raise RuntimeError("VB_STORE=pgvector needs VB_PG_DSN, e.g. postgresql://user:pass@host:5432/vectorbench")
        return cls(dsn, dimension, schema=os.getenv("VB_PG_SCHEMA", "public"),
                   search_mode=os.getenv("VB_PG_SEARCH", "hnsw"),
                   ef_search=int(os.getenv("VB_PG_EF_SEARCH", "40")),
                   pool_max=int(os.getenv("VB_PG_POOL_MAX", "8")))

    def with_search(self, search_mode: str, ef_search: Optional[int] = None,
                    pool_max: int = 2) -> "PgVectorStore":
        """A second handle on the same data with different search settings (used by the benchmark)."""
        return PgVectorStore(self.dsn, self.dimension, schema=self.schema, search_mode=search_mode,
                             ef_search=ef_search or self.ef_search, pool_max=pool_max)

    def close(self) -> None:
        self._pool.close()

    # --- setup ---

    def _configure(self, conn: psycopg.Connection) -> None:
        register_vector(conn)
        conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(self.schema)))
        conn.commit()

    def _init_schema(self) -> None:
        ident = sql.Identifier(self.schema)
        with psycopg.connect(self.dsn, autocommit=True) as conn:
            with conn.transaction():
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK_KEY,))
                conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(ident))
                conn.execute(sql.SQL("""
                    CREATE TABLE IF NOT EXISTS {}.documents (
                        file       text PRIMARY KEY,
                        sha256     text,
                        content    bytea,
                        updated_at timestamptz NOT NULL DEFAULT now())""").format(ident))
                conn.execute(sql.SQL("""
                    CREATE TABLE IF NOT EXISTS {}.chunks (
                        file      text NOT NULL REFERENCES {}.documents(file) ON DELETE CASCADE,
                        idx       int  NOT NULL,
                        chunk     text NOT NULL,
                        embedding vector({}) NOT NULL,
                        PRIMARY KEY (file, idx))""").format(ident, ident, sql.Literal(self.dimension)))
                # Built incrementally as rows arrive; its cost is part of what ingest timings measure.
                conn.execute(sql.SQL("""
                    CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw
                    ON {}.chunks USING hnsw (embedding vector_cosine_ops)""").format(ident))

    # --- reads ---

    def __len__(self) -> int:
        with self._pool.connection() as conn:
            return conn.execute("SELECT count(*) FROM chunks").fetchone()[0]

    def search(self, vector: Sequence[float], k: int,
               file: Optional[str] = None) -> List[Dict[str, Any]]:
        q = np.asarray(vector, dtype=np.float32)
        with self._pool.connection() as conn, conn.transaction():
            if file:
                # Rank one file's chunks exactly. pgvector applies a WHERE filter *after* an HNSW
                # scan, which visits only ef_search candidates, so if the planner ever picked the
                # HNSW index here it could return fewer than k rows. Materializing the file's rows
                # first makes the result independent of the plan; a file has few chunks.
                rows = conn.execute("""
                    WITH f AS MATERIALIZED (SELECT idx, chunk, embedding FROM chunks WHERE file = %s)
                    SELECT %s::text, idx, chunk, embedding <=> %s AS dist FROM f ORDER BY dist LIMIT %s""",
                    (file, file, q, k)).fetchall()
            else:
                if self.search_mode == "exact":
                    conn.execute("SET LOCAL enable_indexscan = off")
                else:
                    # The index returns at most ef_search rows, so it must be at least k.
                    conn.execute("SELECT set_config('hnsw.ef_search', %s, true)",
                                 (str(max(self.ef_search, k)),))
                rows = conn.execute("""
                    SELECT file, idx, chunk, embedding <=> %s AS dist
                    FROM chunks ORDER BY embedding <=> %s LIMIT %s""", (q, q, k)).fetchall()
            hashes = dict(conn.execute("SELECT file, sha256 FROM documents WHERE file = ANY(%s)",
                                       ([r[0] for r in rows],)).fetchall()) if rows else {}
        return [{"id": f"{f}::{idx}", "similarity": 1.0 / (1.0 + float(dist)),
                 "metadata": {"file": f, "index": idx, "chunk": chunk, "file_type": file_type_of(f),
                              "sha256": hashes.get(f)}}
                for f, idx, chunk, dist in rows]

    def file_stats(self) -> Dict[str, Dict[str, Any]]:
        with self._pool.connection() as conn:
            rows = conn.execute("""
                SELECT d.file, d.sha256, count(c.idx)
                FROM documents d LEFT JOIN chunks c USING (file) GROUP BY d.file, d.sha256""").fetchall()
        return {f: {"chunks": n, "sha256": h} for f, h, n in rows}

    def file_sha256(self, filename: str) -> Optional[str]:
        with self._pool.connection() as conn:
            row = conn.execute("SELECT sha256 FROM documents WHERE file = %s", (filename,)).fetchone()
        return row[0] if row else None

    def source(self, filename: str) -> Optional[bytes]:
        """The original file bytes, so a full re-index never depends on any replica's disk."""
        with self._pool.connection() as conn:
            row = conn.execute("SELECT content FROM documents WHERE file = %s", (filename,)).fetchone()
        return bytes(row[0]) if row and row[0] is not None else None

    # --- writes ---

    def replace_file(self, filename: str, chunks: Sequence[str], vectors: Sequence[Sequence[float]],
                     sha256: Optional[str] = None, source: Optional[bytes] = None) -> int:
        if len(chunks) != len(vectors):
            raise ValueError("chunks and vectors must be the same length")
        for v in vectors:
            if len(v) != self.dimension:
                raise ValueError(f"Vector dimension mismatch: expected {self.dimension}, got {len(v)}")
        with self._pool.connection() as conn, conn.transaction():
            # Serialize writers of the same file across every replica; other files proceed in parallel.
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (filename,))
            conn.execute("DELETE FROM documents WHERE file = %s", (filename,))  # cascades to chunks
            conn.execute("INSERT INTO documents (file, sha256, content) VALUES (%s, %s, %s)",
                         (filename, sha256, source))
            with conn.cursor().copy(
                    "COPY chunks (file, idx, chunk, embedding) FROM STDIN WITH (FORMAT BINARY)") as copy:
                copy.set_types(["text", "int4", "text", "vector"])
                for idx, (chunk, vec) in enumerate(zip(chunks, vectors)):
                    copy.write_row((filename, idx, chunk, np.asarray(vec, dtype=np.float32)))
        return len(chunks)

    def delete_file(self, filename: str) -> int:
        with self._pool.connection() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (filename,))
            n = conn.execute("SELECT count(*) FROM chunks WHERE file = %s", (filename,)).fetchone()[0]
            conn.execute("DELETE FROM documents WHERE file = %s", (filename,))
        return n
