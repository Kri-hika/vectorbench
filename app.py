"""VectorBench API: upload documents, search them semantically, and inspect latency and correctness."""
from __future__ import annotations

import logging
import os
import statistics
import tempfile
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import pipeline
from pipeline import Embedder, ExtractionError
from store import VectorLiteStore, VectorStore, open_store

log = logging.getLogger("vectorbench")


class SearchResponseItem(BaseModel):
    id: str
    similarity: float
    metadata: Dict[str, Any]


def _percentiles(vals: List[float]) -> Dict[str, Optional[float]]:
    if not vals:
        return {"p50": None, "p95": None}
    p95 = statistics.quantiles(vals, n=20)[18] if len(vals) >= 2 else vals[0]
    return {"p50": round(statistics.median(vals), 3), "p95": round(p95, 3)}


def create_app(embedder: Optional[Embedder] = None, db_path: Optional[str] = None,
               docs_dir: Optional[str] = None, store: Optional[VectorStore] = None) -> FastAPI:
    """Build the app. Tests pass a lightweight embedder, temp paths or a store; production loads
    the model and opens the store chosen by VB_STORE."""
    db_path = db_path or pipeline.DB_PATH
    docs_dir = docs_dir or pipeline.DOCS_DIR
    state: Dict[str, Any] = {}
    publish_lock = threading.Lock()

    # Per-stage latency of recent searches. Embedding the query is usually the larger share,
    # so it is tracked separately instead of being hidden inside one number.
    lat_total: deque = deque(maxlen=500)
    lat_embed: deque = deque(maxlen=500)
    lat_search: deque = deque(maxlen=500)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Load the model and index before the server accepts traffic, so /health only answers once ready.
        state["embed"] = embedder or pipeline.load_embedder()
        # `is not None`, not `or`: stores define __len__, so an empty store is falsy.
        state["index"] = store if store is not None else open_store(db_path=db_path, dimension=pipeline.EMBED_DIM)
        os.makedirs(docs_dir, exist_ok=True)
        try:
            yield
        finally:
            if store is None:  # a store passed in by the caller is the caller's to close
                state["index"].close()

    app = FastAPI(title="VectorBench API", lifespan=lifespan)
    origins = [o.strip() for o in os.getenv("VB_CORS_ORIGINS", "*").split(",") if o.strip()]
    # Credentials stay off: browsers reject credentialed requests to a wildcard origin anyway.
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])

    def index() -> VectorStore:
        return state["index"]

    @app.get("/health")
    def health():
        return {"ok": True, "vectors": len(index()), "store": index().name}

    @app.get("/metrics")
    def metrics():
        total, embed, search_ = list(lat_total), list(lat_embed), list(lat_search)
        t, e, s = _percentiles(total), _percentiles(embed), _percentiles(search_)
        return {
            "vectors": len(index()),
            "count": len(total),
            "recent": total[-10:],
            # p50_ms/p95_ms are end-to-end (query embedding + index search): what a user waits for.
            "p50_ms": t["p50"], "p95_ms": t["p95"],
            "embed_p50_ms": e["p50"], "embed_p95_ms": e["p95"],
            "search_p50_ms": s["p50"], "search_p95_ms": s["p95"],
            "last_query": state.get("last_query"),
        }

    # Sync endpoints run in FastAPI's thread pool, so a long upload no longer blocks searches.
    @app.get("/search", response_model=List[SearchResponseItem])
    def search(q: str = Query(..., min_length=1, description="Query text"),
               k: int = Query(5, ge=1, le=50),
               file: Optional[str] = Query(None, description="Optional filename filter")):
        t0 = time.perf_counter()
        q_vec = state["embed"]([q])[0]
        t1 = time.perf_counter()
        results = index().search(q_vec, k, file=file)
        t2 = time.perf_counter()
        embed_ms, search_ms = 1000 * (t1 - t0), 1000 * (t2 - t1)
        lat_embed.append(round(embed_ms, 3))
        lat_search.append(round(search_ms, 3))
        lat_total.append(round(embed_ms + search_ms, 3))
        state["last_query"] = {"q": q, "k": k, "file": file, "latency_ms": round(embed_ms + search_ms, 3),
                               "embed_ms": round(embed_ms, 3), "search_ms": round(search_ms, 3)}
        return results

    @app.post("/upload")
    def upload_file(file: UploadFile = File(...)):
        """Upload and index a document. Re-uploading identical content is a no-op;
        re-uploading changed content replaces that file's chunks."""
        try:
            filename = pipeline.safe_filename(file.filename)
        except ExtractionError as e:
            return JSONResponse(status_code=400, content={"error": str(e)})

        content = file.file.read(pipeline.MAX_UPLOAD_BYTES + 1)
        if len(content) > pipeline.MAX_UPLOAD_BYTES:
            return JSONResponse(status_code=413, content={"error": "File exceeds 10 MB limit"})
        file_type = os.path.splitext(filename)[1].lstrip(".").lower()
        sha = pipeline.sha256_bytes(content)

        stats = index().file_stats().get(filename)
        if stats and stats.get("sha256") == sha:
            return {"message": f"{filename} is unchanged; nothing to re-index", "unchanged": True,
                    "chunks": stats["chunks"], "total_vectors": len(index()), "file_type": file_type}

        try:
            extraction = pipeline.extract_text(content, filename)
            text = pipeline.require_text(extraction)
        except ExtractionError as e:
            return JSONResponse(status_code=422, content={"error": str(e)})

        # Embed outside the index lock: this is the slow step, and searches keep running meanwhile.
        chunks = pipeline.chunk_text(text)
        vectors = state["embed"](chunks)

        if index().stores_sources:
            # The database keeps the original next to its chunks in one transaction; no local disk
            # involved, so any replica can serve any request.
            try:
                n = index().replace_file(filename, chunks, vectors, sha256=sha, source=content)
            except Exception:
                log.exception("Failed to index %s", filename)
                return JSONResponse(status_code=500, content={"error": "Failed to index file"})
        else:
            # Stage the file first, swap the index, then publish the file, so disk and index never disagree.
            final_path = os.path.join(docs_dir, filename)
            fd, tmp_path = tempfile.mkstemp(prefix=".upload-", dir=docs_dir)
            try:
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
                with publish_lock:  # index swap + file rename as one step across concurrent uploads
                    n = index().replace_file(filename, chunks, vectors, sha256=sha)
                    os.replace(tmp_path, final_path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                log.exception("Failed to index %s", filename)
                return JSONResponse(status_code=500, content={"error": "Failed to index file"})

        body = {"message": f"Successfully uploaded and ingested {filename}", "unchanged": False,
                "chunks": n, "total_vectors": len(index()), "file_type": file_type,
                "extracted_text_length": len(text)}
        if extraction.pages_without_text:
            body["pages_without_text"] = extraction.pages_without_text
        return body

    @app.get("/files")
    def list_files():
        """Known files with their indexed chunk counts. With the embedded store this also lists files
        in the docs directory that failed to index (count 0); with pgvector the database is the list."""
        stats = index().file_stats()
        names = set(stats)
        if not index().stores_sources:
            names |= {os.path.basename(p) for p in pipeline.list_source_files(docs_dir)}
        out = []
        for name in sorted(names):
            count = stats.get(name, {}).get("chunks", 0)
            out.append({"filename": name, "count": count, "in_database": count > 0})
        return out

    # --- micro-benchmarks of the embedded store itself (throwaway temp directory, any VB_STORE) ---
    # Comparing backends on a real workload is benchmarks/compare_stores.py.

    @app.get("/bench")
    def bench(N: int = Query(500, ge=1, le=50000), k: int = Query(5, ge=1, le=50)):
        import numpy as np
        dim = pipeline.EMBED_DIM
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "bench.db")
            idx = VectorLiteStore(path, dimension=dim)
            X = np.random.randn(N, dim).astype("float32")
            t0 = time.perf_counter()
            idx.replace_file("bench", [""] * N, X.tolist())
            ins_ms = 1000 * (time.perf_counter() - t0) / N
            q = np.random.randn(dim).astype("float32").tolist()
            t1 = time.perf_counter()
            idx.search(q, k)
            search_ms = 1000 * (time.perf_counter() - t1)
            size_mb = os.path.getsize(path) / 1e6
        return {"N": N, "avg_insert_ms": round(ins_ms, 3), "search_ms": round(search_ms, 3),
                "file_MB": round(size_mb, 2), "note": "Bulk insert with a single atomic save"}

    @app.get("/parity")
    def parity(K: int = Query(5, ge=1, le=50)):
        """Check index top-K against an exact NumPy brute-force cosine ranking."""
        import numpy as np
        N, D = 1000, pipeline.EMBED_DIM
        rng = np.random.default_rng(0)
        X = rng.standard_normal((N, D)).astype("float32")
        q = rng.standard_normal(D).astype("float32")
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        sims = Xn @ (q / (np.linalg.norm(q) + 1e-9))
        np_ids = np.argsort(-sims)[:K].tolist()
        with tempfile.TemporaryDirectory() as tmp:
            idx = VectorLiteStore(os.path.join(tmp, "parity.db"), dimension=D)
            idx.replace_file("parity", [""] * N, X.tolist())
            res = idx.search(q.tolist(), K)
        vl_ids = [int(r["id"].split("::")[1]) for r in res]
        return {"ok": set(np_ids) == set(vl_ids), "numpy_topk": np_ids, "vldb_topk": vl_ids}

    return app


app = create_app()
