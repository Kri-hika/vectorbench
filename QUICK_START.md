# Quick Start

Get up and running in **5 minutes**. This guide covers installation, verification, and common issues.

---

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Ingest sample documents
python ingest.py

# Start the API server
uvicorn app:app --reload
```

Open `frontend/index.html` in your browser or visit http://127.0.0.1:8000

---

## Verification Checklist

### 1. Accuracy Test

Click **"✓ Accuracy"** in the Quick Actions panel.

```
✅ Perfect Match!
VectorLiteDB results match NumPy baseline
```

**What this means:** Your search algorithm is mathematically correct. A mismatch indicates a serious bug.

<br>

### 2. Performance Check

Monitor the **Performance** metrics (auto-updates every 5s):

| Metric | Meaning |
|--------|---------|
| **Indexed** | Files currently in the database |
| **Queries** | Total search operations executed |
| **Latency (P95)** | 95th percentile response time |
| **Status** | Visual health indicator |

<br>

**Status Guide:**

```
🟢 Excellent  < 50ms   │ Production-grade performance
🔵 Good      50-100ms  │ Acceptable for most use cases
🟡 OK       100-300ms  │ Usable, but consider optimization
🔴 Slow       > 300ms  │ Action required
```

<br>

### 3. Benchmark Test

Run a quick benchmark to establish baseline performance:

```
Click "⚡ Benchmark" → Tests 500 vectors in ~10s
```

**Key metrics to watch:**
- **Insert speed:** Should be < 5ms/vector on local SSD
- **Search time:** Target < 100ms
- **Warnings:** Yellow alerts indicate environmental issues

> **⚠️ Common Issue:** Insert times > 10ms usually indicate iCloud sync interference.
>
> **Fix:**
> ```bash
> mkdir -p ~/Local/vectorbench-db
> ln -s ~/Local/vectorbench-db/kb.db kb.db
> ```

---

## Performance Expectations

| Scale | Search Latency | File Size | Recommended For |
|------:|---------------:|----------:|:----------------|
| 1K | 5-20ms | ~10MB | Development/testing |
| 10K | 20-100ms | ~100MB | **Production sweet spot** |
| 50K | 100-500ms | ~500MB | Upper practical limit |
| 100K+ | >500ms | >1GB | Consider alternatives |

---

## Key Concepts

### Latency (P50 vs P95)

- **P50 (median):** Half of all requests are faster
- **P95:** 95% of requests complete within this time

We track **P95** because it captures the worst experience most users will encounter. A healthy system keeps P95 < 2× P50.

<br>

### Parity Checks

Validates correctness by comparing VectorLiteDB results against a NumPy brute-force reference implementation across 1,000 random vectors.

<br>

### File Growth

Each 384-dimensional vector + metadata consumes ~2-5KB of storage. Budget approximately **10MB per 1,000 vectors**.

---

## Troubleshooting

<details>
<summary><b>❌ "API not reachable"</b></summary>

The backend server isn't running.

```bash
uvicorn app:app --reload
```

Verify it's accessible at http://127.0.0.1:8000/health
</details>

<details>
<summary><b>🐌 Benchmarks taking >30s for N=500</b></summary>

**Root cause:** macOS iCloud Drive sync

**Solution:**
```bash
# Move database to non-synced location
mkdir -p ~/Local/vectorbench-db
mv kb.db ~/Local/vectorbench-db/
ln -s ~/Local/vectorbench-db/kb.db kb.db

# Verify fix
ls -lah kb.db  # Should show symlink (->)
```

**Why this works:** iCloud adds 50-100x latency to SQLite writes.
</details>

<details>
<summary><b>⚠️ "Mismatch detected" in parity check</b></summary>

Search results don't match the NumPy baseline.

**Possible causes:**
- Outdated VectorLiteDB version
- Corrupted database file
- Floating-point precision edge cases

**Resolution:**
```bash
pip install --upgrade vectorlitedb
python ingest.py  # Rebuild database
```
</details>

<details>
<summary><b>💾 Large database files</b></summary>

**This is normal behavior.** Vector embeddings are large:

```
384 dimensions × 4 bytes (float32) = 1.5KB per vector
+ metadata (variable)
+ SQLite overhead
≈ 2-5KB per document chunk
```

Expected growth: **~10MB per 1,000 indexed chunks**
</details>

---

## Scale Testing

Test how performance degrades with increasing data:

| Profile | Test Sizes | Duration | Purpose |
|:--------|:-----------|:---------|:--------|
| **Quick** | 100, 250, 500 | ~20s | Daily health check |
| **Standard** | 500, 1K, 2K | ~1min | Sprint validation |
| **Thorough** | 1K, 2.5K, 5K | ~3min | Release qualification |

The output graph shows search latency vs database size. **Linear growth is expected** (brute-force algorithm).

---

## Next Steps

- **Experiment:** Upload your own documents and run searches
- **Monitor:** Watch real-time metrics during usage
- **Benchmark:** Test different scales to find your breaking point
- **Learn:** Deep dive into [CONCEPTS.md](CONCEPTS.md)

---

## Decision Matrix

### ✅ Use VectorBench When

- Building personal knowledge bases
- Developing local RAG applications
- Prototyping semantic search features
- Working with **10K-100K documents**
- Prioritizing simplicity over scale

### 🔄 Consider Alternatives When

You need sub-10ms latency, millions of documents, concurrent writes, or distributed deployment.

**Alternatives:** [Chroma](https://www.trychroma.com/), [LanceDB](https://lancedb.com/), [Qdrant](https://qdrant.tech/), [FAISS](https://github.com/facebookresearch/faiss)

---

**Questions?** Check [CONCEPTS.md](CONCEPTS.md) for deeper explanations or [TESTING.md](TESTING.md) for the testing framework.
