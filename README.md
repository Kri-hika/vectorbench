# VectorBench

Local vector database experimentation and benchmarking platform built on VectorLiteDB. Single-file embedded vector DB with semantic search, performance testing, and a web interface.

## What's This For?

Playing around with vector databases locally. Ingests documents, generates embeddings, runs searches, and benchmarks performance. Good for learning how vector DBs work or prototyping RAG applications without external dependencies.

## Stack

- Python 3.10+
- VectorLiteDB (single-file embedded vector DB; JSON body, rewritten on every save)
- Optional: Postgres + pgvector as a second storage backend (`VB_STORE=pgvector`)
- sentence-transformers (all-MiniLM-L6-v2, 384-dim embeddings)
- FastAPI + Uvicorn
- Optional: Docker/docker-compose

## Quick Start

```bash
# Setup
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Ingest some documents and run the API
python ingest.py
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Hit the search endpoint
curl "http://127.0.0.1:8000/search?q=your+query&k=5"

# Or use the CLI
python cli_search.py "example query"
```

Open `frontend/index.html` in a browser for the web interface.

## Learning Resources

If you're new to VectorLiteDB:
- [QUICK_START.md](QUICK_START.md) - 5-minute walkthrough
- [CONCEPTS.md](CONCEPTS.md) - How vector search actually works
- `python learn_vectorlitedb.py` - Interactive experiments

## Web Interface

Two-column layout with search on the right, controls on the left.

Features:
- Document upload (PDF, DOCX, PPTX, XLSX, TXT, MD)
- File-filtered search with dropdown
- Real-time metrics: indexed files, query count, P95 latency
- Benchmark suite with configurable test sizes
- Scale testing across different vector counts
- Accuracy verification against NumPy baseline
- Search history and keyboard shortcuts (⌘T: run all tests, ⌘E: export)

Local dev: just open `frontend/index.html`  
Docker: served via nginx at `http://localhost:5173`

## Docker

Without compose:
```bash
docker build -t vectorbench .
docker run --rm -p 8000:8000 \
  -v "$PWD/docs:/app/docs" \
  -v "$PWD/data:/app/data" vectorbench
```

With compose:
```bash
docker compose up --build
# API: http://127.0.0.1:8000
# Frontend: http://127.0.0.1:5173
```

The index lives in `data/kb.db`. On start, `ingest.py` re-embeds only files that changed since the
last run and drops files that were deleted; `python ingest.py --rebuild` starts from scratch.

## Storage Backends

The API, ingester and CLI run on either store; both pass the same test suite.

| | `vectorlite` (default) | `pgvector` |
|---|---|---|
| Where data lives | one index file, held in memory by the API | Postgres tables (chunks, vectors, original files) |
| Writers | one process | any number of API replicas |
| Search | exact (brute force) | HNSW (approximate) by default, or exact |
| Run it | nothing extra | `docker compose -f docker-compose.yml -f docker-compose.pgvector.yml up --build` |

Ingestion pruning differs on purpose: with `vectorlite` the `docs/` directory is the source of truth, so
files deleted there are dropped from the index. With `pgvector`, uploads live only in the database, so
`ingest.py` prunes only with `--prune`.

## Kubernetes (local, kind)

```bash
docker build -t vectorbench-api:local .
kind create cluster --name vectorbench
kind load docker-image vectorbench-api:local --name vectorbench
kubectl apply -f k8s/vectorbench.yaml
kubectl rollout status deployment/vectorbench-api
kubectl port-forward service/vectorbench-api 8000:8000   # then open frontend/index.html
```

Runs one replica by design: the index is a single file that the API also holds in memory, so
only one process may own it. `replicas: 1` with the `Recreate` strategy enforces that (a
ReadWriteOnce volume limits it to one node, not one pod). Uploaded documents persist on the same volume.

With pgvector (own namespace, so it can run next to the embedded one):

```bash
kubectl apply -f k8s/pgvector/
kubectl -n vectorbench-pg rollout status statefulset/postgres
kubectl -n vectorbench-pg rollout status deployment/vectorbench-api
kubectl -n vectorbench-pg port-forward service/vectorbench-api 8001:8000
python sync_client.py --api http://127.0.0.1:8001 --dir docs/     # load documents through the API
```

Two API replicas share Postgres; the autoscaler in `20-api.yaml` needs metrics-server
(`kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml`,
plus `--kubelet-insecure-tls` on kind). `30-sync-cronjob.yaml` re-syncs the URLs listed in its ConfigMap nightly.

## API Endpoints

```
GET  /health                      # Status, vector count, active store
GET  /search?q=...&k=5&file=...   # Semantic search (optional file filter)
POST /upload                      # Upload document (multipart form)
GET  /files                       # List files with chunk counts
GET  /metrics                     # P50/P95 latency (end-to-end, embed, search), query count
GET  /bench?N=500                 # Benchmark (bulk insert + search, temp dir)
GET  /parity?K=5                  # Accuracy check vs NumPy
```

## Benchmarking

Via web interface:
- Quick benchmark: customizable vector counts (100-2000)
- Scale test: runs `/bench` sequentially across multiple sizes (100/250/500, 500/1K/2K, or 1K/2.5K/5K) and plots latency vs. vector count
- Accuracy verification: compare against NumPy ground truth

Via CLI:
```bash
python bench.py
```

Backend comparison (embedded vs pgvector on the same corpus; writes CSV and a Markdown table to
`benchmarks/results/`):
```bash
VB_PG_DSN=postgresql://vectorbench:vectorbench@localhost:5432/vectorbench \
  python benchmarks/compare_stores.py --sizes 1000,5000,20000 --ef-search 20,40,100
python benchmarks/compare_stores.py --source kb.db --stores vectorlite,pgvector   # your real embeddings
```
Measures ingest time, cost of re-indexing one document in a loaded corpus, p50/p95 search latency,
recall@k against exact search, throughput at several client counts, and storage size. Store timings
exclude embedding. Synthetic recall is not retrieval quality; use `--source kb.db` for realistic vectors.

## Configuration

- Add documents to `docs/` and run `python ingest.py` (or upload via web, or `python sync_client.py --dir docs/`)
- Environment: `VB_STORE` (`vectorlite`|`pgvector`), `VB_DB_PATH`, `VB_DOCS_DIR`, `VB_CORS_ORIGINS`;
  for pgvector `VB_PG_DSN`, `VB_PG_SCHEMA`, `VB_PG_SEARCH` (`hnsw`|`exact`), `VB_PG_EF_SEARCH`, `VB_PG_POOL_MAX`
- Filter searches by filename: `/search?file=sample.txt&q=...`
- Supported formats: `.txt`, `.md`, `.pdf`, `.docx`, `.pptx`, `.xlsx`

## Known Limitations

By design:
- Embedded store: brute-force search, one writing process, whole file rewritten per commit
  (see `benchmarks/compare_stores.py` for where that starts to matter)
- Bring-your-own embeddings

## Performance Notes

### macOS iCloud Sync Warning

`/bench` and `/parity` now run in a system temp directory, so they need no setup.

If your project lives under `~/Documents` (synced by iCloud by default), keep the main index outside it to avoid 50-100x write slowdowns. Either point the app at another path, or symlink `kb.db` (saves write through the link):

```bash
mkdir -p ~/Local/vectorbench-db
export VB_DB_PATH=~/Local/vectorbench-db/kb.db    # or: ln -s ~/Local/vectorbench-db/kb.db kb.db
```

Check if you're affected by iCloud sync: `ls -la ~/Documents | head -3` (look for `@` symbols in permissions)

### SQLite Write Characteristics

VectorLiteDB uses `PRAGMA synchronous=FULL` for data safety. This means:
- Search: very fast (brute force up to 100k vectors)
- Insert: slower (~1-5ms/vector on SSD, up to 300ms on cloud storage)
- Data integrity: zero data loss, even on power failure

Typical benchmarks:
- N=100: 0.5-1s (local SSD) vs 30s (iCloud)
- N=500: 2-5s (local SSD) vs 5min (iCloud)
- N=1000: 4-8s (local SSD) vs 10min (iCloud)

For production workloads needing faster writes, consider chromadb, lancedb, qdrant, or FAISS. VectorBench prioritizes safety and simplicity for learning/prototyping.

## Maintenance

Clean up cache and temp files:
```bash
./cleanup.sh
```

Removes `.DS_Store`, `__pycache__`, `.pyc`, `.pytest_cache`, logs, and editor temp files.

## Testing

See [TESTING.md](TESTING.md) for the full test suite including accuracy parity checks, concurrency tests, and crash recovery validation.

```bash
python run_comprehensive_tests.py
```

Service and store tests (`tests/test_api.py`, `tests/test_store.py`, `tests/test_sync_client.py`) run on
both backends; the pgvector half needs a database:
```bash
VB_TEST_PG_DSN=postgresql://vectorbench:vectorbench@localhost:5432/vectorbench pytest tests -q
```
