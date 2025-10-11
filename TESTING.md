# Testing Framework

Comprehensive test suite for VectorLiteDB covering correctness, performance, durability, and edge cases.

---

## Overview

This framework systematically validates VectorLiteDB across six dimensions:

| Dimension | Purpose | Tools |
|:----------|:--------|:------|
| **Functional Correctness** | CRUD operations, filters, metrics | PyTest suite |
| **Persistence & Durability** | Crash recovery, file portability | Crash simulation |
| **Performance Characteristics** | Throughput, latency, scaling | Benchmark scripts |
| **Accuracy & Parity** | NumPy baseline comparison | Statistical validation |
| **Robustness & Edge Cases** | Unicode, large metadata, stress | Fuzzing, stress tests |
| **Resource Usage** | RAM, CPU, file descriptors | Profiling tools |

---

## Quick Start

### Run Full Suite

```bash
python run_comprehensive_tests.py
```

**Duration:** ~5-10 minutes  
**Output:** Console logs + CSV files

<br>

### Run Essentials Only

```bash
python run_comprehensive_tests.py --quick
```

**Duration:** ~1-2 minutes  
**Covers:** Smoke tests, basic parity, minimal benchmarks

<br>

### Run by Category

```bash
# Correctness tests only
python run_comprehensive_tests.py --tests-only

# Performance experiments only
python run_comprehensive_tests.py --experiments-only
```

---

## Test Structure

### Correctness Tests (`tests/`)

| File | Purpose | Key Assertions |
|:-----|:--------|:---------------|
| `test_smoke.py` | Basic CRUD operations | Insert, retrieve, search, delete |
| `test_metrics.py` | Distance metric behavior | Cosine, L2, dot product rankings |
| `test_accuracy_parity.py` | NumPy baseline comparison | Top-K set equality |
| `test_persistence_crash.py` | Durability guarantees | Reopen after crash, data integrity |
| `test_metadata_filters.py` | Filter predicate correctness | Complex filter combinations |

<br>

### Performance Experiments (`experiments/`)

| File | Purpose | Output |
|:-----|:--------|:-------|
| `latency_sweep.py` | Scaling analysis (1K→50K) | `latency_sweep.csv` |
| `concurrency_probe.py` | Multi-reader behavior | Console logs |
| `big_metadata.py` | Large payload stress test | Memory profiles |

---

## Success Criteria

### ✅ Functional Correctness

```python
# All tests pass
assert all_tests_passed == True

# Filters work as specified
assert filtered_results == expected_results

# Wrong dimensions rejected
with pytest.raises(DimensionMismatchError):
    db.insert("id", wrong_dimension_vector)

# Empty DB operations safe
assert db.search(query, top_k=5) == []
```

<br>

### ✅ Persistence & Durability

```python
# After normal shutdown
assert len(db_reopened) == len(db_original)
assert db_reopened.get("sample_id").metadata == original_metadata

# After simulated crash
assert db_recovered.is_operational() == True
assert db_recovered.row_count() > 0  # Some data survived
```

<br>

### ✅ Performance Characteristics

```python
# Insert throughput stable
assert std_dev(insert_times) < mean(insert_times) * 0.2

# Search scales linearly
assert correlation(data_size, latency) > 0.95

# File growth proportional
assert file_size_mb / vector_count ≈ 0.01  # ~10KB per vector
```

<br>

### ✅ Accuracy & Parity

```python
# Top-K matches reference
numpy_top_k = brute_force_search(vectors, query, k=5)
vldb_top_k = vectorlitedb.search(query, top_k=5)

# Set equality (order-agnostic due to ties)
assert set(numpy_top_k) == set(vldb_top_k)
```

<br>

### ✅ Robustness

```python
# Large metadata doesn't crash
db.insert("large", vector, {"text": "x" * 1_000_000})

# Concurrent reads work
with ThreadPoolExecutor(max_workers=10) as executor:
    results = executor.map(lambda i: db.search(query), range(100))
    assert all(len(r) == 5 for r in results)

# Resource usage bounded
assert max(memory_samples) < baseline_memory * 3
```

---

## Performance Analysis

### Understanding Benchmarks

The `latency_sweep.py` experiment generates a CSV file with:

```csv
N,avg_insert_ms,search_ms,file_MB,total_insert_time_s
1000,1.2,15.3,9.8,1.2
5000,1.4,78.5,49.2,7.0
10000,1.5,156.8,98.5,15.0
25000,1.6,392.1,245.6,40.0
50000,1.8,784.5,491.2,90.0
```

### Key Insights

**Insert Throughput**
```
Good:  < 2ms per vector (stable)
OK:    2-5ms per vector
Poor:  > 5ms per vector (investigate environment)
```

**Search Latency**
```
1K vectors   → ~15ms   (excellent)
10K vectors  → ~150ms  (good)
50K vectors  → ~750ms  (approaching limits)
100K vectors → ~1500ms (consider migration)
```

**File Growth**
```
Expected: ~10MB per 1K vectors (384-dim + metadata)
Variance: ±20% is normal (depends on metadata size)
Warning:  >15MB per 1K = excessive metadata
```

### Scaling Patterns

**Linear Scaling (Expected)**
```
O(N) search time is expected for brute-force.
Doubling data size doubles search time.
```

**Sub-linear (Caching)**
```
If search time grows slower than O(N), you may be
hitting OS page cache. Test with larger datasets
that exceed RAM.
```

**Super-linear (Bottleneck)**
```
If search time grows faster than O(N), investigate:
• Disk I/O saturation
• Memory pressure / swapping
• Background processes interfering
```

---

## Concurrency Behavior

VectorLiteDB uses SQLite, which has specific concurrency characteristics:

### Multiple Readers

```python
# ✅ Supported
reader1 = VectorLiteDB("kb.db")
reader2 = VectorLiteDB("kb.db")
reader3 = VectorLiteDB("kb.db")

# All can search simultaneously
results1 = reader1.search(query)
results2 = reader2.search(query)
results3 = reader3.search(query)
```

### Readers + Writer

```python
# ⚠️ Behavior depends on SQLite config
writer = VectorLiteDB("kb.db")
reader = VectorLiteDB("kb.db")

# Writes may block reads or vice versa
# Use WAL mode for better concurrency:
# PRAGMA journal_mode=WAL
```

### Multiple Writers

```python
# ❌ Not supported
# SQLite allows one writer at a time
# Additional writers will block or error
```

### Best Practices

1. **Read-heavy workloads:** Open multiple reader instances
2. **Write-heavy workloads:** Use single writer with batching
3. **Mixed workloads:** Enable WAL mode, separate reader/writer pools
4. **High concurrency:** Consider client-server architecture (Chroma, Qdrant)

---

## Metadata Testing

### Size Limits

```python
# Small metadata (typical)
metadata = {"title": "Doc 1", "page": 42}  # ~50 bytes

# Medium metadata
metadata = {"title": "...", "content": "..." * 100}  # ~5KB

# Large metadata (stress test)
metadata = {"content": "x" * 1_000_000}  # 1MB

# Test all sizes to understand behavior
```

### Performance Impact

| Metadata Size | Insert Impact | Search Impact | Storage Impact |
|:--------------|:--------------|:--------------|:---------------|
| < 1KB | Negligible | Negligible | ~10MB / 1K vectors |
| 1-10KB | +10-20% | Negligible | ~15-20MB / 1K vectors |
| 10-100KB | +50-100% | Negligible | ~50-100MB / 1K vectors |
| \> 100KB | Significant | Negligible | Linear with size |

### Recommendations

- **Keep metadata compact:** Store IDs/references, not full documents
- **Separate storage:** Store large text in separate KV store, reference by ID
- **Index efficiently:** Only store searchable fields in metadata

---

## Output Artifacts

### CSV Files

**`latency_sweep.csv`**

Columns:
- `N`: Number of vectors indexed
- `avg_insert_ms`: Mean insert time per vector
- `search_ms`: Single search latency
- `file_MB`: Database file size
- `total_insert_time_s`: Total ingestion duration

**Usage:**
```python
import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv('latency_sweep.csv')
plt.plot(df['N'], df['search_ms'])
plt.xlabel('Vectors')
plt.ylabel('Search Latency (ms)')
plt.title('VectorLiteDB Scaling')
plt.show()
```

<br>

### Console Output

Real-time progress with:
- Test names and status (PASS/FAIL)
- Performance metrics
- Memory usage samples
- Warning messages for anomalies

---

## Use Case Guidelines

### ✅ Recommended Use Cases

| Scenario | Why VectorBench Works Well |
|:---------|:---------------------------|
| **Personal Knowledge Base** | 1-10K documents, local-first, simple setup |
| **Prototype/MVP** | Fast iteration, no infrastructure, embedded |
| **Jupyter Notebooks** | Single-file DB, easy to share, reproducible |
| **Small Internal Tools** | 10-50K documents, read-heavy, low concurrency |
| **Local RAG** | Offline operation, privacy, deterministic |

<br>

### ❌ Not Recommended

| Scenario | Why You Need Something Else |
|:---------|:----------------------------|
| **Multi-tenant SaaS** | Need isolation, horizontal scaling, backups |
| **High Concurrency** | SQLite write limitations, connection pooling |
| **Millions of Vectors** | O(N) search too slow, need ANN algorithms |
| **Distributed Systems** | Single-file architecture, no replication |
| **Sub-10ms Latency** | Brute force can't achieve at scale |

**Better alternatives:** Chroma (ease of use), Qdrant (performance), Pinecone (managed), FAISS (raw speed)

---

## Best Practices

### 1. Embedding Consistency

```python
# ✅ Good: Fixed model and dimensions
model = SentenceTransformer('all-MiniLM-L6-v2')  # 384-dim
db = VectorLiteDB("kb.db", dimension=384)

# ❌ Bad: Mixing models
embedding1 = model1.encode(text)  # 384-dim
embedding2 = model2.encode(text)  # 768-dim
```

### 2. Index Lifecycle Management

```python
# Incremental updates (append-only)
if not os.path.exists("kb.db"):
    db = VectorLiteDB("kb.db", dimension=384)
else:
    db = VectorLiteDB("kb.db")  # Reopen existing

# Rebuild from scratch
if os.path.exists("kb.db"):
    os.remove("kb.db")
db = VectorLiteDB("kb.db", dimension=384)  # Fresh start
```

### 3. Backup Strategy

```bash
# Simple file copy (ensure no active writes)
cp kb.db kb.backup.db

# With timestamp
cp kb.db "kb.$(date +%Y%m%d_%H%M%S).db"

# Automated backup
# Add to cron or scheduled task
```

### 4. Observability

```python
import time
import logging

# Log performance metrics
start = time.time()
results = db.search(query, top_k=5)
latency = time.time() - start

logging.info(f"Search latency: {latency*1000:.2f}ms")
logging.info(f"Database size: {len(db)} vectors")

# Track P50/P95
latencies.append(latency)
p50 = np.percentile(latencies, 50)
p95 = np.percentile(latencies, 95)
```

---

## Troubleshooting

<details>
<summary><b>Import Errors</b></summary>

```bash
# Install all dependencies
pip install -r requirements.txt

# Verify versions
pip list | grep -E "(vectorlitedb|numpy|sentence-transformers)"
```
</details>

<details>
<summary><b>Permission Errors</b></summary>

```bash
# Make scripts executable
chmod +x run_comprehensive_tests.py
chmod +x cleanup.sh

# Check file ownership
ls -la kb.db
```
</details>

<details>
<summary><b>Memory Issues</b></summary>

```python
# Reduce test sizes in experiments/latency_sweep.py
SIZES = [1000, 5000, 10000]  # Instead of [1K, 10K, 50K]

# Use --quick flag
python run_comprehensive_tests.py --quick
```
</details>

<details>
<summary><b>Timeout Issues</b></summary>

```bash
# Skip long-running experiments
python run_comprehensive_tests.py --tests-only

# Or run experiments separately
python experiments/latency_sweep.py
```
</details>

<details>
<summary><b>Accuracy Parity Failures</b></summary>

**Possible causes:**
- NumPy version incompatibility
- Vector dimension mismatch
- Distance metric mismatch
- Floating-point precision edge cases

**Debug:**
```python
# Check versions
import numpy as np
print(f"NumPy version: {np.__version__}")

# Verify dimensions
print(f"Test vectors shape: {test_vectors.shape}")
print(f"DB dimension: {db.dimension}")
```
</details>

<details>
<summary><b>Persistence Test Failures</b></summary>

**Indicates:**
- VectorLiteDB bug
- Filesystem issues
- Disk corruption

**Action:**
```bash
# Check filesystem
df -h  # Disk space
fsck   # Filesystem check (unmount first)

# Update VectorLiteDB
pip install --upgrade vectorlitedb

# Enable verbose logging
LOGLEVEL=DEBUG python tests/test_persistence_crash.py
```
</details>

---

## Advanced Testing

### Custom Experiments

Create new experiments in `experiments/`:

```python
# experiments/my_custom_test.py
import vectorlitedb
import numpy as np
import time

def test_dimension_scaling():
    """Test how performance scales with embedding dimensions"""
    
    dimensions = [128, 256, 384, 512, 768]
    results = []
    
    for dim in dimensions:
        db = VectorLiteDB(f"test_{dim}d.db", dimension=dim)
        
        # Generate test data
        vectors = np.random.randn(1000, dim).astype('float32')
        
        # Measure insert time
        start = time.time()
        for i, vec in enumerate(vectors):
            db.insert(f"vec_{i}", vec.tolist(), {"index": i})
        insert_time = time.time() - start
        
        # Measure search time
        query = np.random.randn(dim).astype('float32')
        start = time.time()
        db.search(query.tolist(), top_k=10)
        search_time = time.time() - start
        
        results.append({
            'dimension': dim,
            'insert_ms': insert_time / len(vectors) * 1000,
            'search_ms': search_time * 1000
        })
        
        os.remove(f"test_{dim}d.db")
    
    return results

if __name__ == "__main__":
    results = test_dimension_scaling()
    print("\nDimension Scaling Results:")
    print("-" * 50)
    for r in results:
        print(f"{r['dimension']}d: "
              f"insert={r['insert_ms']:.2f}ms, "
              f"search={r['search_ms']:.2f}ms")
```

---

## Contributing

### Test Guidelines

1. **Naming:** Use `test_` prefix for pytest discovery
2. **Docstrings:** Explain what and why, not how
3. **Cleanup:** Always remove temporary files
4. **Determinism:** Use fixed random seeds
5. **Independence:** Tests should not depend on each other

### Example Test Template

```python
def test_feature_name():
    """
    Test description: Clear, concise explanation of what's being tested
    
    Expected behavior: What should happen in the passing case
    
    Edge cases: What boundary conditions are being validated
    """
    # Setup
    db = VectorLiteDB("test_temp.db", dimension=384)
    
    try:
        # Execute
        result = db.some_operation()
        
        # Verify
        assert result == expected_value, f"Expected {expected_value}, got {result}"
        
    finally:
        # Cleanup (always runs)
        if os.path.exists("test_temp.db"):
            os.remove("test_temp.db")
```


Use these tests to **understand VectorLiteDB's behavior** and make **informed decisions** about whether it's the right tool for your use case.

---

**Questions?** Check [CONCEPTS.md](CONCEPTS.md) for deeper explanations or [README.md](README.md) for setup instructions.
