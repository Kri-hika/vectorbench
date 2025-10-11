# Testing Framework

Comprehensive testing and benchmarking suite for VectorLiteDB. Tests **functional correctness**, **performance**, **durability**, and **edge cases**.

---

## What's Tested

### Functional Correctness

- Insert/get/delete/re-insert semantics
- Distance metrics *(cosine, L2, dot)* and ranking
- Metadata filters with various predicates
- Empty DB behavior and wrong-dimension rejections

<br>

### Persistence & Durability

- Normal close and reopen *(data integrity)*
- Crash recovery during inserts
- File portability across machines/OS/Python versions

<br>

### Performance

- Insert throughput vs N *(1k → 50k)*
- Query latency vs N and top_k
- File size growth vs N and metadata size
- Distance metric performance differences

<br>

### Accuracy

- Top-k results vs **NumPy brute-force baseline**
- Stability when vectors have near-tie scores

<br>

### Robustness

- Duplicate ID handling
- Large metadata blobs *(multi-KB)* and Unicode
- Burst inserts followed by immediate searches
- Concurrent readers with single writer

<br>

### Resource Usage

- Peak RAM during ingest/search
- CPU usage patterns
- File descriptor leaks in long-running loops

---

## Quick Start

### Run all tests
```bash
python run_comprehensive_tests.py
```

<br>

### Run only essentials *(faster)*
```bash
python run_comprehensive_tests.py --quick
```

<br>

### Run only performance experiments
```bash
python run_comprehensive_tests.py --experiments-only
```

<br>

### Run only correctness tests
```bash
python run_comprehensive_tests.py --tests-only
```

---

## Test Structure

### Correctness Tests (`tests/`)

| Test File | Purpose |
|-----------|---------|
| `test_smoke.py` | *Basic CRUD and search* |
| `test_metrics.py` | *Distance metric behavior* |
| `test_accuracy_parity.py` | **Accuracy vs NumPy** |
| `test_persistence_crash.py` | *Persistence and crash recovery* |
| `test_metadata_filters.py` | *Metadata filtering* |

<br>

### Performance Experiments (`experiments/`)

| Experiment File | Purpose |
|-----------------|---------|
| `latency_sweep.py` | **Performance at different scales** |
| `concurrency_probe.py` | *Concurrent access patterns* |
| `big_metadata.py` | *Large metadata pressure tests* |

---

## Understanding Results

### Good Results

#### ✅ Functional

- All tests pass
- Filters behave as expected
- Wrong dimensions throw errors
- Empty DB calls don't crash

<br>

#### ✅ Persistence

- After normal shutdown: `len(db)` stable, metadata intact
- After crash: DB reopens without corruption

<br>

#### ✅ Performance

- **Insert**: *Stable average time, no surprising slowdowns*
- **Search**: *Latency scales roughly O(N), stays under 100-200ms for ~10k vectors*
- **File size**: *Proportional growth, no runaway bloat*

<br>

#### ✅ Accuracy

- Top-k from VectorLiteDB **matches NumPy** *(accounting for ties)*

<br>

#### ✅ Robustness

- Large metadata doesn't cause crashes
- Reads during inserts work consistently
- RAM doesn't grow indefinitely, CPU usage consistent

---

## Key Insights

### Performance

| Aspect | Expected Behavior |
|--------|-------------------|
| **Scaling** | *Search time scales linearly O(N)* |
| **Dimensions** | *Higher dimensions = slower search* |
| **Metrics** | *Cosine vs dot vs L2 may differ in performance* |
| **Top-K** | *Larger K = longer search* |
| **File size** | *Grows linearly with N and D* |

<br>

### Concurrency

*Key questions to answer:*

- Can multiple readers access DB **simultaneously**?
- Can readers access **during writes**?
- What happens with **multiple writers**?
- Multiple connections to **same file**?
- Failure modes **under stress**?

<br>

### Metadata

*Key areas to investigate:*

- Maximum storable metadata size
- Performance impact on search
- Memory patterns with large metadata
- Unicode/special character handling
- Filtering performance

---

## Output Files

### CSV Files

**`latency_sweep.csv`** - *Performance data*

| Column | Description |
|--------|-------------|
| `N` | *Number of vectors* |
| `avg_insert_ms` | *Average insert time* |
| `search_ms` | **Search latency** |
| `file_MB` | *Database file size* |
| `total_insert_time_s` | *Total insert duration* |

Use this data to **plot performance curves**.

<br>

### Console Output

*Real-time information:*
- Performance metrics
- Memory usage tracking
- Concurrency observations
- Error patterns and failure modes

---

## Use Cases

### ✅ Right Use Cases

- **Local/offline RAG**
- **Personal knowledge bases**
- Notebooks and prototypes
- Small internal tools
- **10k-100k vector range**

<br>

### ❌ Wrong Use Cases

- Multi-tenant applications
- Heavy concurrency
- Millions of vectors with **strict SLOs**
- Distributed systems

---

## Best Practices

### 1. Embedding Consistency

Pick a model, fix dimensions, keep it **consistent** across all operations.

<br>

### 2. Index Lifecycle

- **Rebuilding often**: Use *deterministic IDs*
- **Appending**: Avoid *duplicate IDs*

<br>

### 3. Backups

Copy `.db` file while process isn't writing. Treat it like a **standard SQLite file**.

<br>

### 4. Observability

*Log these metrics:*
- Insert durations
- DB length
- **P50/P95 latency**

---

## Troubleshooting

### Import Errors

```bash
pip install -r requirements.txt
```

<br>

### Permission Errors

```bash
chmod +x run_comprehensive_tests.py
```

<br>

### Memory Issues

- Reduce test sizes in experiment files
- Use `--quick` flag

<br>

### Timeout Issues

- Some experiments take **several minutes**
- Use `--tests-only` to skip long experiments

---

## Test-Specific Issues

### Accuracy parity failures

**Possible causes**:
- NumPy version incompatibility
- Vector dimensions mismatch

<br>

### Persistence failures

**Possible causes**:
- VectorLiteDB version issues
- File permissions or disk space

<br>

### Concurrency failures

> **Note**: Behavior may vary by VectorLiteDB version. Document actual behavior for your use case.

---

## Advanced Experiments

### Optional Tests to Add

1. **Keyword + vector hybrid search**
2. **Distance metric A/B testing**
3. **Portability** *(build on machine A, query on machine B)*
4. **Heavy delete-and-reinsert cycles**

<br>

### Creating Custom Experiments

Create new experiments in `experiments/` following existing patterns:

```python
# experiments/my_custom_test.py
import vectorlitedb
import time

# Your test logic here
```

---

## Contributing

### Guidelines for New Tests

1. **Follow naming conventions**
2. **Include comprehensive docstrings**
3. **Add cleanup code** for temporary files
4. **Update this README** with test descriptions
5. **Ensure deterministic** and repeatable tests

<br>

### Example Test Structure

```python
def test_my_feature():
    """
    Test description: what it does and why
    
    Expected behavior: what should happen
    """
    # Setup
    db = create_test_db()
    
    # Execute
    result = db.my_operation()
    
    # Verify
    assert result == expected_value
    
    # Cleanup
    cleanup_test_db()
```

---

> This framework helps you **understand VectorLiteDB's behavior and limits**. Use results to decide if it's suitable for your use case.
