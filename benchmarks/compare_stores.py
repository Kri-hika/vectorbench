"""Compare vector store backends on the same corpus: when is the embedded store enough?

For each corpus size it loads the corpus document by document (one commit per document, as uploads
do), then measures:
  ingest_s        total time to load the corpus
  update_ms       time to re-index one document once the corpus is loaded (median of 5); this is
                  what a single upload costs, and it is where a whole-file store and a database diverge
  p50/p95_ms      single-client search latency
  recall@k        overlap with exact brute-force top-k (1.0 = exact; HNSW trades some for speed)
  qps@c           searches per second with c concurrent clients
  storage_mb      index file size (vectorlite) or table + index size (pgvector)

Store timings exclude embedding: queries and chunks are pre-computed vectors, so only the store is measured.

Sources:
  --source synthetic       clustered unit vectors (default). Useful for scaling; recall on real
                           embeddings differs, so do not quote synthetic recall as retrieval quality.
  --source path/kb.db      vectors from an existing VectorLiteDB index (your real embeddings),
                           resampled with small noise to reach each size.

Example:
  VB_PG_DSN=postgresql://postgres:postgres@localhost:5432/vectorbench \\
  python benchmarks/compare_stores.py --sizes 1000,5000,20000 --ef-search 20,40,100
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from store import VectorLiteStore  # noqa: E402

DIM = 384


# --- data ---

def _unit(x: np.ndarray) -> np.ndarray:
    return (x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-12)).astype(np.float32)


def synthetic(n: int, n_queries: int, rng: np.random.Generator):
    """Clustered data: real embeddings cluster by topic, which is what makes approximate search hard."""
    centers = rng.standard_normal((max(8, int(np.sqrt(n))), DIM))
    def draw(m):
        return _unit(centers[rng.integers(0, len(centers), m)] + 0.35 * rng.standard_normal((m, DIM)))
    return draw(n), draw(n_queries)


def from_index(path: str, n: int, n_queries: int, rng: np.random.Generator):
    """Resample real embeddings from a VectorLiteDB file to the requested size."""
    from vectorlitedb import VectorLiteDB
    base = np.asarray(list(VectorLiteDB(path).vectors.values()), dtype=np.float32)
    if len(base) < 10:
        raise SystemExit(f"{path} has only {len(base)} vectors; index some documents first")
    def draw(m):
        picks = base[rng.integers(0, len(base), m)]
        return _unit(picks + 0.02 * rng.standard_normal(picks.shape) * np.abs(picks).mean())
    return draw(n), draw(n_queries)


def exact_topk(X: np.ndarray, Q: np.ndarray, k: int) -> List[set]:
    sims = Q @ X.T  # both unit-normalized: cosine similarity
    top = np.argpartition(-sims, kth=min(k, X.shape[0] - 1), axis=1)[:, :k]
    return [set(row.tolist()) for row in top]


# --- measurement ---

def load(store, X: np.ndarray, doc_size: int) -> float:
    t0 = time.perf_counter()
    for d, start in enumerate(range(0, len(X), doc_size)):
        block = X[start:start + doc_size].tolist()  # plain floats: VectorLiteDB stores JSON
        store.replace_file(f"doc{d}.txt", [""] * len(block), block, sha256=str(d))
    return time.perf_counter() - t0


def update_cost_ms(store, X: np.ndarray, doc_size: int, rng: np.random.Generator, reps: int = 5) -> float:
    n_docs = (len(X) + doc_size - 1) // doc_size
    times = []
    for _ in range(reps):
        d = int(rng.integers(0, n_docs))
        block = X[d * doc_size:(d + 1) * doc_size].tolist()
        t0 = time.perf_counter()
        store.replace_file(f"doc{d}.txt", [""] * len(block), block, sha256=str(d))
        times.append(1000 * (time.perf_counter() - t0))
    return statistics.median(times)


def row_of(hit_id: str, doc_size: int) -> int:
    name, idx = hit_id.split("::")
    return int(name[3:-4]) * doc_size + int(idx)


def search_stats(store, Q: np.ndarray, truth: List[set], k: int, doc_size: int) -> Dict[str, float]:
    for q in Q[:10]:  # warm caches and connections
        store.search(q, k)
    lat, recalls = [], []
    for q, t in zip(Q, truth):
        t0 = time.perf_counter()
        hits = store.search(q, k)
        lat.append(1000 * (time.perf_counter() - t0))
        recalls.append(len({row_of(h["id"], doc_size) for h in hits} & t) / k)
    p95 = statistics.quantiles(lat, n=20)[18] if len(lat) >= 20 else max(lat)
    return {"p50_ms": statistics.median(lat), "p95_ms": p95, "recall": float(np.mean(recalls))}


def throughput(store, Q: np.ndarray, k: int, clients: int, seconds: float = 3.0) -> float:
    stop, count, lock = time.perf_counter() + seconds, [0], threading.Lock()

    def client(offset: int):
        i = offset
        while time.perf_counter() < stop:
            store.search(Q[i % len(Q)], k)
            i += clients
            with lock:
                count[0] += 1

    t0 = time.perf_counter()
    with ThreadPoolExecutor(clients) as pool:
        list(pool.map(client, range(clients)))
    return count[0] / (time.perf_counter() - t0)


def pg_storage_mb(store) -> float:
    with store._pool.connection() as conn:
        b = conn.execute("SELECT pg_total_relation_size('chunks') + pg_total_relation_size('documents')").fetchone()[0]
    return b / 1e6


# --- driver ---

def run(args) -> List[Dict[str, object]]:
    rng = np.random.default_rng(args.seed)
    rows: List[Dict[str, object]] = []
    clients = [int(c) for c in args.concurrency.split(",")]
    efs = [int(e) for e in args.ef_search.split(",")]
    stores = args.stores.split(",")
    dsn = os.getenv("VB_PG_DSN")
    if "pgvector" in stores and not dsn:
        raise SystemExit("set VB_PG_DSN to benchmark pgvector, or pass --stores vectorlite")

    for n in [int(s) for s in args.sizes.split(",")]:
        X, Q = (synthetic(n, args.queries, rng) if args.source == "synthetic"
                else from_index(args.source, n, args.queries, rng))
        truth = exact_topk(X, Q, args.k)
        print(f"\n== {n} vectors, {len(Q)} queries, k={args.k}, {args.doc_size} chunks per document ==")

        def record(store_name, store, ingest_s, update_ms, storage_mb):
            s = search_stats(store, Q, truth, args.k, args.doc_size)
            row = {"store": store_name, "vectors": n, "ingest_s": ingest_s, "update_ms": update_ms,
                   "p50_ms": s["p50_ms"], "p95_ms": s["p95_ms"], f"recall@{args.k}": s["recall"],
                   "storage_mb": storage_mb}
            for c in clients:
                row[f"qps@{c}"] = throughput(store, Q, args.k, c, args.qps_seconds)
            rows.append(row)
            print("  " + "  ".join(f"{k}={_fmt(v)}" for k, v in row.items() if k != "vectors"))

        if "vectorlite" in stores:
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "kb.db")
                s = VectorLiteStore(path, dimension=DIM)
                ingest = load(s, X, args.doc_size)
                upd = update_cost_ms(s, X, args.doc_size, rng)
                record("vectorlite (exact)", s, ingest, upd, os.path.getsize(path) / 1e6)

        if "pgvector" in stores:
            from store_pg import PgVectorStore
            schema = f"bench_{uuid.uuid4().hex[:10]}"
            s = PgVectorStore(dsn, DIM, schema=schema, ef_search=efs[0], pool_max=max(clients) + 2)
            try:
                ingest = load(s, X, args.doc_size)
                upd = update_cost_ms(s, X, args.doc_size, rng)
                with s._pool.connection() as conn:
                    conn.execute("ANALYZE chunks")
                size_mb = pg_storage_mb(s)
                for ef in efs:  # same data, different search settings: the recall/latency curve
                    h = s.with_search("hnsw", ef, pool_max=max(clients) + 2)
                    try:
                        record(f"pgvector hnsw ef={ef}", h, ingest, upd, size_mb)
                    finally:
                        h.close()
                e = s.with_search("exact", pool_max=max(clients) + 2)
                try:
                    record("pgvector (exact)", e, ingest, upd, size_mb)
                finally:
                    e.close()
            finally:
                if not args.keep:
                    import psycopg
                    with psycopg.connect(dsn, autocommit=True) as conn:
                        conn.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
                s.close()
    return rows


def _fmt(v: object) -> str:
    if isinstance(v, float):
        return f"{v:.3f}" if v < 10 else f"{v:.1f}"
    return str(v)


def write_outputs(rows: List[Dict[str, object]], out_dir: str, args) -> str:
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.join(out_dir, f"compare-{stamp}")
    keys = list(rows[0].keys())
    with open(base + ".csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    with open(base + ".md", "w") as f:
        f.write(f"source={args.source} k={args.k} doc_size={args.doc_size} queries={args.queries} "
                f"seed={args.seed} machine={os.uname().sysname}/{os.uname().machine}\n\n")
        f.write("| " + " | ".join(keys) + " |\n|" + "---|" * len(keys) + "\n")
        for r in rows:
            f.write("| " + " | ".join(_fmt(r[k]) for k in keys) + " |\n")
    return base


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--stores", default="vectorlite,pgvector")
    p.add_argument("--sizes", default="1000,5000,20000", help="corpus sizes in vectors")
    p.add_argument("--source", default="synthetic", help="'synthetic' or a path to a VectorLiteDB kb.db")
    p.add_argument("--queries", type=int, default=200)
    p.add_argument("--k", type=int, default=10)
    p.add_argument("--doc-size", type=int, default=50, help="chunks per document (one commit each)")
    p.add_argument("--concurrency", default="1,4,8", help="client counts for throughput")
    p.add_argument("--qps-seconds", type=float, default=3.0)
    p.add_argument("--ef-search", default="40", help="pgvector HNSW ef_search values to sweep, e.g. 20,40,100")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default="benchmarks/results")
    p.add_argument("--keep", action="store_true", help="keep the pgvector benchmark schemas")
    args = p.parse_args(argv)

    rows = run(args)
    base = write_outputs(rows, args.out, args)
    print(f"\nWrote {base}.csv and {base}.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
