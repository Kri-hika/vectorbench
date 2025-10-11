# VectorBench

Local vector database experimentation and benchmarking platform built on VectorLiteDB. Single-file embedded vector DB with semantic search, performance testing, and a web interface.

## What's This For?

Playing around with vector databases locally. Ingests documents, generates embeddings, runs searches, and benchmarks performance. Good for learning how vector DBs work or prototyping RAG applications without external dependencies.

## Stack

- Python 3.10+
- VectorLiteDB (single-file SQLite-based vector DB)
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
  -v "$PWD/kb.db:/app/kb.db" vectorbench
```

With compose:
```bash
docker compose up --build
# API: http://127.0.0.1:8000
# Frontend: http://127.0.0.1:5173
```

## API Endpoints

```
GET  /health                      # Status and vector count
GET  /search?q=...&k=5&file=...   # Semantic search (optional file filter)
POST /upload                      # Upload document (multipart form)
GET  /files                       # List files with chunk counts
GET  /metrics                     # P50/P95 latency, query count
GET  /bench?N=500                 # Benchmark (100-2000 vectors)
GET  /parity?K=5                  # Accuracy check vs NumPy
GET  /scale                       # Multi-scale performance test
```

## Benchmarking

Via web interface:
- Quick benchmark: customizable vector counts (100-2000)
- Scale test: multiple sizes with timing
- Accuracy verification: compare against NumPy ground truth

Via CLI:
```bash
python bench.py
```

## Configuration

- Add documents to `docs/` and run `python ingest.py` (or upload via web)
- Change distance metric in `VectorLiteDB()`: `cosine` (default), `l2`, `dot`
- Filter searches by filename: `/search?file=sample.txt&q=...`
- Supported formats: `.txt`, `.md`, `.pdf`, `.docx`, `.pptx`, `.xlsx`

## Known Limitations

By design:
- Brute force search only (good for ~10k-100k vectors)
- No concurrent writes
- Bring-your-own embeddings

## Performance Notes

### macOS iCloud Sync Warning

If benchmarks are taking >30s for N=500, you're probably hitting iCloud sync overhead. macOS syncs `~/Documents` by default, causing 50-100x slowdown on SQLite writes.

Fix: symlink the database outside iCloud sync:
```bash
mkdir -p ~/Local/vectorbench-db
ln -s ~/Local/vectorbench-db/kb.db kb.db
```

Check if you're affected: `ls -la ~/Documents | head -3` (look for `@` symbols in permissions)

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
