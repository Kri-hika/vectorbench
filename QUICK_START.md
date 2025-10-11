# Quick Start

Get VectorBench running and verify it works. Takes about **5 minutes**.

---

## Setup

```bash
# Install dependencies
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Ingest documents and start API
python ingest.py
uvicorn app:app --reload

# Open web interface
open frontend/index.html
```

**API endpoint**: http://127.0.0.1:8000

---

## Verify It Works

### 1. Check Search Accuracy

**Action**: Click **"✓ Accuracy"** in *Quick Actions* (web interface)

**Expected result**:
```
✅ Perfect Match!
VectorLiteDB results match NumPy baseline
```

**What it means**: Search results are mathematically correct. If this fails, something's wrong with the algorithm.

<br>

### 2. Check Performance

Look at the **Performance** section *(auto-refreshes every 5s)*:

| Metric | Description |
|--------|-------------|
| **Indexed** | Number of files in database |
| **Queries** | Total searches executed |
| **Latency (P95)** | *95% of searches complete within this time* |
| **Status** | Color-coded performance indicator |

<br>

#### **Status Colors**:

- 🟢 **Green** *(< 50ms)* → **Excellent**
- 🔵 **Blue** *(50-100ms)* → **Good**  
- 🟡 **Yellow** *(100-300ms)* → **OK**
- 🔴 **Red** *(> 300ms)* → **Slow**

<br>

### 3. Run a Benchmark

**Action**: Click **"⚡ Benchmark"** in *Quick Actions* *(tests 500 vectors)*

**Watch for**:
- Insert speed **< 5ms** per vector
- Search time **< 100ms**
- Any yellow warnings about slow inserts

> **⚠️ Note**: Slow inserts *(> 10ms)* usually mean iCloud sync interference.  
> **Fix**: Move database to `~/Local/vectorbench-db/`

---

## Understanding the Metrics

### Latency

Time from search request to results. Users notice delays over **100ms**.

<br>

### P50 vs P95

- **P50** *(median)*: Half of searches are this fast or faster
- **P95**: 95% of searches are this fast or faster

**Why P95 matters**: It catches slow outliers that median might hide.

<br>

### Parity Check

Compares VectorLiteDB to a *"gold standard"* NumPy implementation. Both search **1000 random vectors** - if top results match, accuracy is verified.

---

## Performance Expectations

| Documents | Search Time | File Size | Notes |
|-----------|-------------|-----------|-------|
| **1,000** | *5-20ms* | ~10MB | *Development* |
| **10,000** | *20-100ms* | ~100MB | **Typical usage** |
| **50,000** | *100-500ms* | ~500MB | *Upper limit* |
| **100,000+** | *>500ms* | >1GB | *Consider alternatives* |

---

## Common Issues

### "API not reachable"

**Cause**: API server isn't running

**Fix**:
```bash
uvicorn app:app --reload
```

<br>

### Slow benchmarks *(>30s for N=500)*

**Cause**: iCloud Drive is syncing your database

**Fix**:
```bash
mkdir -p ~/Local/vectorbench-db
ln -s ~/Local/vectorbench-db/kb.db kb.db
```

<br>

### "Mismatch detected" in parity check

**Cause**: VectorLiteDB results don't match NumPy baseline

**Fix**: Check your VectorLiteDB version or rebuild the database

<br>

### Large file sizes

**Explanation**: *Normal behavior*. Each chunk with **384-dim vector** + metadata = ~2-5 KB

**Expected**: ~10 MB per **1,000 vectors**

---

## Testing Scale

Click **"📊 Scale"** in *Quick Actions* or expand **Advanced Tests** for custom profiles:

| Profile | Sizes | Time |
|---------|-------|------|
| **Quick** | *100, 250, 500 vectors* | ~20s |
| **Standard** | *500, 1K, 2K vectors* | ~1min |
| **Thorough** | *1K, 2.5K, 5K vectors* | ~3min |

**Output**: Graph showing search time vs database size. *Linear growth is expected* (brute force algorithm).

---

## Next Steps

1. **Upload** your own documents via the web interface
2. **Search** and watch metrics in real-time
3. **Benchmark** with different sizes to find your limits
4. **Learn** more in [CONCEPTS.md](CONCEPTS.md)

---

## When to Use VectorBench

### ✅ Good For

- Personal knowledge bases
- Local RAG apps
- Prototyping
- **10k-100k documents**

### ❌ Consider Alternatives

**chromadb, lancedb, qdrant, FAISS** when you need:

- Sub-10ms search times
- Millions of documents
- Concurrent writes
- Distributed deployment
