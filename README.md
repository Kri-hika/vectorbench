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
- **[CONCEPTS.md](CONCEPTS.md)** - Deep dive into concepts
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
The frontend provides a modern, responsive two-column interface with comprehensive search and diagnostic capabilities:

- **Two-Column Layout**: Left panel for controls and metrics, right panel for search and results
- **Document Upload**: Multi-format support (.txt, .md, .pdf, .docx, .pptx, .xlsx) with automatic extraction
- **Performance Metrics**: Real-time tracking of indexed files, queries, P95 latency, and status
- **Smart Search**: Dropdown file filter, recent search history, keyboard shortcuts
- **Advanced Diagnostics**: 
  - Quick Actions (one-click accuracy verification)
  - Benchmark testing with customizable vector counts (100-2,000)
  - Scale testing with profiles (quick/standard/thorough)
  - Accuracy verification with configurable K
  - System health monitoring
- **Enhanced UX**: Collapsible sections, skeleton loaders, status indicators, and export functionality
- **Keyboard Shortcuts**: ⌘T (Run All Tests), ⌘E (Export Results), Enter (Search)

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
- `GET /search?q=query&k=5&file=optional` - Semantic search with optional file filter
- `POST /upload` - Upload and ingest new documents (multipart/form-data)
- `GET /files` - List all files with database status and chunk counts
- `GET /metrics` - Performance metrics (P50/P95 latency, query count)
- `GET /bench?N=500` - Run benchmark test (default N=500, customizable 100-2000)
- `GET /parity?K=5` - Verify search accuracy vs NumPy (default K=5)
- `GET /scale` - Run scalability test across multiple vector counts

## 🔍 **Built-in Observability**

The web interface provides comprehensive real-time monitoring and diagnostics:

**Performance Metrics (Auto-updating):**
- Indexed Files count
- Total Queries executed
- P95 Latency tracking
- Performance Status (Excellent/Good/OK/Slow)

**Quick Actions:**
- **✓ Accuracy** → One-click accuracy verification

**Advanced Tests:**
- **⚡ Quick Benchmark** → Customizable insert/search performance test (100-2,000 vectors)
- **📊 Scale Test** → Multi-scale performance analysis (Quick/Standard/Thorough profiles)
- **✓ Accuracy Verification** → Detailed parity check vs NumPy baseline (configurable K)
- **💚 System Health** → Comprehensive health check with file statistics

**Header Actions:**
- **Run All Tests** (⌘T) → Execute full diagnostic suite
- **Export Results** (⌘E) → Copy formatted report to clipboard

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
