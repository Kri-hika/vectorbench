# VectorLiteDB Comprehensive Testing Framework

This directory contains a complete testing and experimentation framework for VectorLiteDB, designed to understand its capabilities, limits, and behavior patterns from every angle.

## 🎯 What This Tests

### A. Functional Correctness
- **Insert/Get/Delete/Re-insert semantics** (by ID)
- **Distance metrics**: cosine, L2, dot → ranking differences
- **Metadata filters**: correctness and stability under varied predicates
- **Empty DB behavior** and wrong-dimension rejections

### B. Persistence & Durability
- **Reopen after normal close** (same length, same IDs, same metadata)
- **Reopen after crash** during insert (partial writes, survivability)
- **File portability** (copy kb.db to another machine/OS/Python version)

### C. Performance Envelopes
- **Insert throughput** vs N (1k → 5k → 10k → 25k → 50k)
- **Query latency** vs N and top_k
- **File size growth** vs N and metadata size
- **Metric sensitivity** (cosine/L2/dot latency differences)

### D. Accuracy & Parity
- **Compare top-k** from VectorLiteDB to NumPy brute-force implementation
- **Spot-check stability** when vectors are near-ties

### E. Robustness & Edges
- **Duplicate IDs** (overwrite? error? verify actual behavior)
- **Large metadata blobs** (multi-KB chunks) and Unicode handling
- **Stress**: burst inserts → immediate searches; interleaving reads/writes
- **Concurrency**: multiple read clients while single writer runs

### F. Resource Usage
- **Peak RAM** during ingest/search (via psutil sampling)
- **CPU usage** during queries
- **File descriptor leaks** (long-running loops)

## 🚀 Quick Start

### Run All Tests
```bash
python run_comprehensive_tests.py
```

### Run Only Essential Tests (Quick)
```bash
python run_comprehensive_tests.py --quick
```

### Run Only Performance Experiments
```bash
python run_comprehensive_tests.py --experiments-only
```

### Run Only Correctness Tests
```bash
python run_comprehensive_tests.py --tests-only
```

## 📁 Test Structure

### Correctness Tests (`tests/`)
- **`test_smoke.py`** - Basic CRUD and search functionality
- **`test_metrics.py`** - Distance metric behavior
- **`test_accuracy_parity.py`** - Accuracy vs NumPy brute-force
- **`test_persistence_crash.py`** - Persistence and crash recovery
- **`test_metadata_filters.py`** - Metadata filtering depth tests

### Performance Experiments (`experiments/`)
- **`latency_sweep.py`** - Performance across different scales
- **`concurrency_probe.py`** - Concurrency behavior testing
- **`big_metadata.py`** - Large metadata pressure tests

## 📊 Understanding Results

### What "Good" Looks Like

#### Functional
- ✅ All tests pass
- ✅ Filters behave exactly as predicates specify
- ✅ Wrong dimensions throw appropriate errors
- ✅ Empty DB calls don't crash

#### Persistence
- ✅ After normal shutdown: `len(db)` stable, random spot-checks show intact metadata
- ✅ After crash: DB reopens and reports sane count (no corruption)

#### Performance
- ✅ **Insert**: stable average insert time, no surprising slowdowns
- ✅ **Search**: latency scales roughly linearly with N, stays acceptable (<100-200ms for ~10k vectors)
- ✅ **File size**: proportional growth, no runaway bloat

#### Accuracy
- ✅ Top-k set from VectorLiteDB == top-k set from NumPy (ties aside) for all metrics

#### Robustness
- ✅ Large metadata/chunks don't cause crashes
- ✅ Reads during inserts either work or fail consistently
- ✅ Resource usage: RAM doesn't creep indefinitely, CPU consistent with brute-force expectations

## 🔍 Key Insights to Look For

### Performance Characteristics
1. **Linear scaling**: Search time should scale roughly O(N)
2. **Dimension impact**: Higher dimensions = slower search
3. **Metric differences**: cosine vs dot vs L2 may have different performance
4. **Top-K impact**: Larger K values should take longer
5. **File size**: Should grow roughly linearly with N and D

### Concurrency Behavior
1. Can multiple readers access the DB simultaneously?
2. Can readers access the DB while a writer is active?
3. What happens with multiple writers?
4. Does the DB support multiple connections to the same file?
5. What are the failure modes under stress?

### Metadata Handling
1. Maximum metadata size that can be stored
2. Performance impact of large metadata on search
3. Memory usage patterns with large metadata
4. Unicode and special character handling
5. Filtering performance with large metadata

## 📈 Generated Output Files

### CSV Files
- **`latency_sweep.csv`** - Performance data across different scales
  - Columns: N, avg_insert_ms, search_ms, file_MB, total_insert_time_s
  - Use this to plot performance curves

### Console Output
- Real-time performance metrics
- Memory usage tracking
- Concurrency behavior observations
- Error patterns and failure modes

## 🛠️ Operational Guidance

### Right Use Cases
- ✅ Local/offline RAG
- ✅ Personal knowledge bases
- ✅ Notebooks and prototypes
- ✅ Small internal tools
- ✅ 10k-100k vector range (order-of-magnitude)

### Wrong Use Cases
- ❌ Multi-tenant applications
- ❌ Heavy concurrency requirements
- ❌ Millions of vectors with strict latency SLOs
- ❌ Distributed systems

### Best Practices
1. **Embedding model discipline**: Pick a model, fix the dimension, keep it consistent
2. **Index lifecycle**: 
   - If rebuilding often: keep ingest idempotent (deterministic IDs)
   - If appending: remove `os.remove(DB_PATH)` and avoid duplicate IDs
3. **Backups**: Treat the .db like a SQLite file—copy while process is not writing
4. **Observability**: Log insert durations, DB length, query latency p50/p95

## 🔧 Troubleshooting

### Common Issues

#### Import Errors
```bash
pip install -r requirements.txt
```

#### Permission Errors
```bash
chmod +x run_comprehensive_tests.py
```

#### Memory Issues
- Reduce test sizes in the experiment files
- Use `--quick` flag for essential tests only

#### Timeout Issues
- Some experiments may take several minutes
- Use `--tests-only` to skip time-consuming experiments

### Test-Specific Issues

#### Accuracy Parity Failures
- Check NumPy version compatibility
- Verify vector dimensions match between tests

#### Persistence Test Failures
- May indicate VectorLiteDB version issues
- Check file permissions and disk space

#### Concurrency Test Failures
- Expected behavior may vary by VectorLiteDB version
- Document the actual behavior for your use case

## 📚 Next-Level Experiments

### Optional Advanced Tests
1. **Keyword + vector hybrid**: Filter by keyword first, then vector search
2. **Distance metric A/B**: Expose toggles in frontend for different metrics
3. **Portability**: Build DB on machine A, query on machine B
4. **Deletion behavior**: Heavy delete-and-reinsert cycles

### Custom Experiments
Create your own test files in the `experiments/` directory following the patterns in the existing files.

## 🤝 Contributing

When adding new tests:
1. Follow the existing naming conventions
2. Include comprehensive docstrings
3. Add cleanup code to remove temporary files
4. Update this README with new test descriptions
5. Ensure tests are deterministic and repeatable

## 📞 Support

If you encounter issues:
1. Check the console output for specific error messages
2. Verify all dependencies are installed
3. Try running individual test files to isolate issues
4. Check VectorLiteDB version compatibility
5. Review the generated CSV files for performance insights

---

**Remember**: This testing framework is designed to help you understand VectorLiteDB's behavior and limits. Use the results to make informed decisions about whether it's suitable for your specific use case.



