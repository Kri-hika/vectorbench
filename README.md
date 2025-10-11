# VectorBench

**Local vector database experimentation and benchmarking** — Build semantic search apps with **VectorLiteDB**, a single-file embedded vector DB.

## Why VectorBench?
- **Experiment locally**: Reproducible, offline, and minimal — perfect for learning vector databases
- **Comprehensive tooling**: Document ingestion, embeddings, metadata filters, search API, persistence, and benchmarking
- **Built-in observability**: Real-time metrics, latency tracking, and parity checks

## Stack
- Python 3.10+
- vectorlitedb (v0.1.0+)
- sentence-transformers (`all-MiniLM-L6-v2`, 384-dim)
- FastAPI + Uvicorn
- (Optional) PyTest for sanity checks
- Optional Docker & docker-compose for one-command run

## 🎓 **New to VectorLiteDB? Start Here!**

- **[QUICK_START.md](QUICK_START.md)** - 5-minute test drive with real questions
- **[UNDERSTANDING_VECTORLITEDB.md](UNDERSTANDING_VECTORLITEDB.md)** - Deep dive into concepts
- **[Interactive Learning](learn_vectorlitedb.py)** - Hands-on experiments

```bash
# Try the interactive learning lab
python learn_vectorlitedb.py
```

## Setup
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Maintenance

### Cleanup Temporary Files
Remove cache files, macOS metadata, and other temporary files:
```bash
./cleanup.sh
```

This script removes:
- `.DS_Store` files (macOS metadata)
- `__pycache__` directories (Python cache)
- `.pyc` files (compiled Python)
- `.pytest_cache` (test cache)
- `*.log` files
- Editor temporary files (`*~`, `*.swp`)

Run this periodically to keep your project clean!

## Ingest docs and run
```bash
python ingest.py
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
# Now hit: http://127.0.0.1:8000/search?q=hello&k=5
```

### CLI search
```bash
python cli_search.py "example query"
```

### Benchmarks
```bash
python bench.py
```

## Frontend
The frontend provides a modern, responsive interface for semantic search with the following features:

- **Smart API Detection**: Automatically detects the correct API endpoint for local development vs Docker deployment
- **Search History**: Remembers your last 10 searches for quick re-execution
- **File Upload**: Upload documents in multiple formats (.txt, .md, .pdf, .docx, .pptx, .xlsx) directly through the web interface
- **Enhanced UX**: Loading states, error handling, and visual feedback
- **Keyboard Support**: Press Enter to search

### Local Development
Open `frontend/index.html` in your browser (or serve it). It calls the API at `http://127.0.0.1:8000` by default when opened from file://

### Docker Deployment
The frontend is served via nginx with proper API proxying at `http://localhost:5173`

## Docker (without compose)
```bash
docker build -t vectorbench .
docker run --rm -p 8000:8000 -v "$PWD/docs:/app/docs" -v "$PWD/kb.db:/app/kb.db" vectorbench
```

## Docker Compose
```bash
docker compose up --build
# API: http://127.0.0.1:8000/health
# Frontend: http://127.0.0.1:5173
```

The Docker Compose setup includes:
- **API Service**: FastAPI backend with automatic document ingestion
- **Frontend Service**: Nginx serving the frontend with API proxy configuration
- **Automatic Networking**: Frontend automatically communicates with backend
- **Volume Mounts**: Persistent storage for documents and vector database

## API Endpoints

- `GET /health` - Check API status and vector count
- `GET /search?q=query&k=5&file=optional` - Semantic search
- `POST /upload` - Upload and ingest new documents
- `GET /files` - List all available files in the knowledge base

## 🔍 **Built-in Observability**

The web interface includes real-time monitoring:

- **`GET /metrics`** - Live latency tracking (p50/p95)
- **`GET /bench`** - On-demand performance testing
- **`GET /parity`** - Accuracy verification vs NumPy

**Web Interface Buttons:**
- **Refresh Health** → API status and vector count
- **Refresh Metrics** → Search latency statistics  
- **Run Quick Bench** → Performance test with 5k vectors
- **Run Parity Check** → Verify search accuracy

## Customize
- Drop documents (`.txt`, `.md`, `.pdf`, `.docx`, `.pptx`, `.xlsx`) inside `docs/` and re-run `ingest.py` OR use the web upload feature
- Change distance metric: `cosine` (default), `l2`, or `dot` in `VectorLiteDB(...)`
- Use `filter` in `/search` (e.g., filter by filename via `?file=sample_1.txt`)
- Upload files directly through the web interface without manual ingestion

## Supported File Types
- **Text Files**: `.txt`, `.md` - Direct text processing
- **PDF Files**: `.pdf` - Text extraction using PyPDF2
- **Word Documents**: `.docx` - Text extraction from paragraphs
- **PowerPoint**: `.pptx` - Text extraction from slides and shapes
- **Excel**: `.xlsx` - Text extraction from all sheets and cells

## Limitations (by design)
- Brute force search, comfortable up to ~10k–100k vectors
- No concurrent writes
- Bring-your-own-embeddings

## ⚠️ Performance Notes

### macOS iCloud Sync Issue
If you're experiencing slow benchmark performance (>30 seconds for N=500):

**Cause:** macOS iCloud Drive syncing `~/Documents` folder interferes with SQLite database writes, causing 50-100x slowdown.

**Solution:** This repo stores database files in `~/Local/vectorbench-db/` (outside iCloud sync):
- `kb.db` is symlinked from project root
- Temporary benchmark files use local storage
- Code remains in Git-tracked location

**Manual Setup (if needed):**
```bash
mkdir -p ~/Local/vectorbench-db
ln -s ~/Local/vectorbench-db/kb.db kb.db
```

**To check if you're affected:**
```bash
ls -la ~/Documents | head -3
# Look for @ symbols after permissions (drwx------@) = iCloud synced
```

### SQLite Write Performance
VectorLiteDB uses SQLite with `PRAGMA synchronous=FULL` mode, which prioritizes **data safety over speed**:

**Performance characteristics:**
- ✅ **Search**: Very fast (brute force up to 100k vectors)
- ⚠️ **Insert**: Slower (~1-5ms per vector on SSD, up to 300ms on cloud storage)
- ✅ **Data integrity**: Zero data loss, even on power failure

**Benchmark expectations:**
- N=100 vectors: 0.5-1 seconds (local SSD) vs 30 seconds (iCloud)
- N=500 vectors: 2-5 seconds (local SSD) vs 5 minutes (iCloud)
- N=1000 vectors: 4-8 seconds (local SSD) vs 10 minutes (iCloud)

**Why this matters:** The batch optimization in this repo helps reduce transaction overhead, but cannot eliminate the disk sync latency imposed by SQLite's durability guarantees. This is by design and ensures your data is never corrupted.

**For production use cases requiring faster writes**, consider:
- **chromadb** - Better write performance, similar API
- **lancedb** - Built on Apache Arrow, much faster
- **qdrant** - Production-grade with Docker support
- **FAISS** - Fastest, but no persistence by default

VectorBench is optimized for **learning, prototyping, and local RAG applications** where the safety-speed trade-off is appropriate.
