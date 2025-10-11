# Understanding Vector Search

A hands-on guide to vector databases. Learn by experimentation, not memorization.

---

## What You'll Learn

This guide answers four fundamental questions through **interactive experiments**:

1. **Correctness:** Are my search results accurate?
2. **Performance:** How fast is it really?
3. **Durability:** What happens when things break?
4. **Scalability:** Where are the limits?

Each experiment takes 1-5 minutes and produces real, measurable results.

---

## Interface Overview

```
┌─────────────────────────┬──────────────────────────┐
│ Control Panel (Left)    │ Results Panel (Right)    │
├─────────────────────────┼──────────────────────────┤
│ 📤 Document Upload      │ 🔍 Search Interface      │
│ 📊 Performance Metrics  │ 🕐 Recent Queries        │
│ ⚡ Quick Actions         │ 📄 Search Results        │
│ 📈 Latency Visualization│                          │
│ 🧪 Advanced Diagnostics │                          │
└─────────────────────────┴──────────────────────────┘
```

### Quick Actions

One-click testing with sensible defaults:

```
⚡ Benchmark    → 500 vectors, ~10s
✓ Accuracy     → NumPy parity check
🔄 Health      → System diagnostics
📊 Scale       → Quick scaling profile
```

### Advanced Diagnostics

Customizable test parameters for deep analysis:

- **Benchmark:** 100 / 500 / 1K / 2K vectors
- **Scale Test:** Quick / Standard / Thorough profiles
- **Accuracy:** Top-5 / Top-10 / Top-20 verification
- **Health:** Comprehensive system report

### Performance Metrics

Live dashboard (5-second refresh):

| Metric | Description |
|:-------|:------------|
| **Indexed** | Documents in database |
| **Queries** | Total searches executed |
| **P95 Latency** | 95th percentile response time |
| **Status** | Color-coded health indicator |

---

## Experiment 1: Verify Correctness

**Time:** 2-3 seconds

**Question:** *Is VectorLiteDB returning the correct results?*

### Procedure

1. Navigate to http://localhost:8000
2. Click **"✓ Accuracy"** in Quick Actions
3. Observe results

### Expected Output

```
✅ Accuracy Verified

Perfect Match!
VectorLiteDB results are identical to the gold-standard
NumPy brute-force implementation.

Test Details:
• Algorithm: Cosine similarity
• Test vectors: 1,000 random samples
• Top-K compared: 5 results
• Baseline: NumPy (reference)
• System: VectorLiteDB (test)
```

### Interpretation

| Result | Meaning | Action |
|:-------|:--------|:-------|
| ✅ **Perfect Match** | Results are mathematically correct | No action needed |
| ⚠️ **Near Match** | Tie-breaking differences only | Acceptable (floating-point precision) |
| ❌ **Mismatch** | Algorithm error detected | Update VectorLiteDB or rebuild DB |

> **Technical Note:** Minor differences in ordering can occur when multiple documents have nearly identical scores (e.g., 0.85234 vs 0.85233). This is normal floating-point behavior and doesn't affect search quality.

---

## Experiment 2: Measure Performance

**Time:** Continuous (live monitoring)

**Question:** *How fast are my searches?*

### Procedure

Monitor the **Performance** panel in the left sidebar. Metrics auto-refresh every 5 seconds.

### Status Indicators

```
🟢 Excellent   < 50ms    Production-grade, no optimization needed
🔵 Good       50-100ms   Acceptable for most use cases
🟡 OK        100-300ms   Noticeable delay, consider optimization
🔴 Slow        > 300ms   User experience impacted, action required
```

### Metric Definitions

**P95 Latency (95th Percentile)**

95% of all search requests complete faster than this value. We track P95 instead of average because:

- Captures worst-case user experience
- Reveals performance outliers
- Better indicator of system stability

**Good performance:** P95 < 2× P50

**Status Calculation**
- Indexed file count
- Query volume
- Latency percentiles
- Combined health score

> **Pro Tip:** Users perceive latency differently based on context:
> - **< 100ms:** Feels instant
> - **100-300ms:** Noticeable but acceptable
> - **> 300ms:** Frustratingly slow

---

## Experiment 3: Find Performance Limits

**Time:** 2 seconds - 1 minute (depending on test size)

**Question:** *How many documents can I index before performance degrades?*

### Procedure

**Option A: Quick Test**
1. Click **"⚡ Benchmark"** (tests 500 vectors)

**Option B: Custom Test**
1. Expand **"Advanced Tests"**
2. Select vector count (100 / 500 / 1K / 2K)
3. Click **"Run Benchmark"**

### Sample Results

```
✓ Benchmark Complete

Configuration:
  Vectors: 500
  Dimensions: 384
  Metric: cosine

Performance:
  Insert: 0.8ms/vector (total: 400ms)
  Search: 45.2ms (1K queries)
  Storage: 12.3 MB

Assessment: Good Performance ✓
Search latency within acceptable range for production use.
```

### Key Metrics

| Metric | Good | Acceptable | Poor |
|:-------|-----:|----------:|-----:|
| **Insert Speed** | < 2ms | 2-10ms | > 10ms |
| **Search Latency** | < 50ms | 50-200ms | > 200ms |
| **Storage Efficiency** | ~2KB/vec | ~5KB/vec | > 10KB/vec |

### Warning Signs

```
⚠️ Slow Inserts Detected (15.2ms avg)

Likely causes:
• Project stored on iCloud Drive or network storage
• Slow disk I/O performance
• Background sync processes interfering

Recommended fix:
Move database to local, non-synced storage:
  mkdir -p ~/Local/vectorbench-db
  mv kb.db ~/Local/vectorbench-db/
  ln -s ~/Local/vectorbench-db/kb.db kb.db
```

> **Root Cause:** VectorLiteDB uses SQLite with `PRAGMA synchronous=FULL`, which forces disk writes for durability. Cloud-synced folders add network latency to every write operation, causing 50-100× slowdowns.

---

## Experiment 4: Test Scaling Behavior

**Time:** 20 seconds - 3 minutes

**Question:** *How does performance degrade as data grows?*

### Procedure

1. Expand **"Advanced Tests"** → **"Scale Test"**
2. Select profile:

| Profile | Test Sizes | Duration | Use Case |
|:--------|:-----------|:---------|:---------|
| **Quick** | 100, 250, 500 | ~20s | Daily health checks |
| **Standard** | 500, 1K, 2K | ~1min | Sprint validation |
| **Thorough** | 1K, 2.5K, 5K | ~3min | Release qualification |

3. Click **"Run Scale Test"**
4. Observe real-time progress and chart

### Output Visualization

```
  Search Latency (ms)
       ↑
   120 │                        •
   100 │                   •
    80 │              •
    60 │         •
    40 │    •
    20 │•
     0 └─────────────────────────────→
       100   250   500   1K   2K   5K
                 Vectors
```

### Interpreting Results

**Linear Growth (Expected)**
```
Latency increases proportionally with data size.
This is normal for brute-force search algorithms.
```

**Steep Curve (Warning)**
```
Non-linear growth indicates you're approaching
practical limits. Consider migration to ANN-based
solutions (Chroma, Qdrant, FAISS).
```

**Flat Curve (Unusual)**
```
Performance isn't scaling with data. Possible causes:
• Test size too small to show differences
• Aggressive caching
• Bottleneck elsewhere in system
```

---

## Experiment 5: Test Data Durability

**Time:** 10-15 seconds

**Question:** *Will my data survive a crash?*

### Procedure

```bash
python -c "
from tests.test_persistence_crash import test_normal_persistence
test_normal_persistence()
"
```

### Expected Output

```
✅ PASS: Data persisted correctly
  - Database reopened successfully
  - Vector count intact
  - Metadata preserved
  - No corruption detected
```

### Failure Modes

```
❌ FAIL: Data integrity compromised

This is a serious issue indicating:
• VectorLiteDB version bug
• Unreliable storage medium
• Filesystem corruption
• Insufficient write permissions

Action required:
1. Implement regular backups
2. Consider enabling SQLite WAL mode
3. Verify storage medium reliability
4. Check filesystem for errors
```

---

## Technical Concepts

### Parity Checks

**Definition:** Validation that VectorLiteDB produces identical results to a reference implementation.

**Implementation:**
1. Generate 1,000 random 384-dim vectors
2. Index in both VectorLiteDB and NumPy
3. Execute identical queries
4. Compare top-K results (accounting for ties)

**Why it matters:** Without parity checks, you can't trust your search results are correct.

<br>

### Latency Percentiles

| Percentile | What It Measures |
|:-----------|:-----------------|
| **P50 (Median)** | Typical user experience |
| **P95** | Worst experience for 95% of users |
| **P99** | Outliers and edge cases |

**Why P95?** It balances between capturing most user experiences while filtering extreme outliers that might be measurement errors.

<br>

### Brute Force vs ANN

**Brute Force (VectorLiteDB)**
```
✓ 100% accurate results
✓ Simple implementation
✓ Predictable behavior
✗ O(N) time complexity
✗ Doesn't scale to millions
```

**ANN (Approximate Nearest Neighbor)**
```
✓ Sub-linear time complexity
✓ Scales to billions of vectors
✗ ~95-99% recall (trade accuracy for speed)
✗ Complex implementation
✗ Harder to tune
```

<br>

### Performance Status

Algorithm for status indicator:

```python
if p95_latency < 50:
    return "🟢 Excellent"
elif p95_latency < 100:
    return "🔵 Good"
elif p95_latency < 300:
    return "🟡 OK"
else:
    return "🔴 Slow"
```

---

## FAQ

<details>
<summary><b>Q: Why do parity checks sometimes show different result orderings?</b></summary>

**A:** When multiple documents have nearly identical similarity scores (e.g., 0.8523 vs 0.8522), the ordering between them is arbitrary. This is due to floating-point precision limits and doesn't affect search quality. As long as the **set** of results matches, the check passes.

Example:
```
NumPy:       [doc3, doc7, doc2, doc9, doc1]
VectorLiteDB: [doc7, doc3, doc2, doc9, doc1]

Result: ✅ PASS (docs 3 and 7 are tied)
```
</details>

<details>
<summary><b>Q: My search is consistently slow. What should I do?</b></summary>

**A:** Follow this diagnostic tree:

1. **Check Status indicator**
   - Green/Blue: No action needed
   - Yellow/Red: Continue troubleshooting

2. **Run Scale Test**
   - Linear growth: Normal brute-force behavior
   - Steep curve: Approaching scale limits

3. **Check indexed document count**
   - < 10K: Should be fast, investigate environment
   - 10K-50K: Expected to be slower
   - \> 50K: Consider migration to ANN-based solution

4. **Verify environment**
   - Not on cloud-synced storage
   - Fast SSD with good I/O
   - Sufficient RAM (1GB+ for 10K vectors)
</details>

<details>
<summary><b>Q: Database file size is growing rapidly. Is this a problem?</b></summary>

**A:** This is **normal behavior**. Here's the math:

```
Per-vector storage:
  384 dims × 4 bytes = 1,536 bytes (vector)
  + ~500-2000 bytes (metadata)
  + ~500 bytes (SQLite overhead)
  = 2.5-4 KB per vector

Expected growth:
  1K vectors → ~10 MB
  10K vectors → ~100 MB
  50K vectors → ~500 MB
```

If growth is **significantly higher**, you may have:
- Excessive metadata per document
- Large text chunks not properly summarized
- Duplicate entries

Check with: `SELECT COUNT(*), AVG(LENGTH(metadata)) FROM vectors;`
</details>

<details>
<summary><b>Q: What's the difference between Quick Actions and Advanced Tests?</b></summary>

**A:**

**Quick Actions** → One-click testing with production defaults
- Benchmark: 500 vectors
- Accuracy: Top-5 verification
- Scale: Quick profile

**Advanced Tests** → Full control for specialized testing
- Benchmark: 100-2,000 vectors
- Accuracy: Top-5 to Top-20
- Scale: Quick/Standard/Thorough profiles

Use **Quick Actions** for daily health checks. Use **Advanced Tests** when you need specific test parameters or deeper analysis.
</details>

<details>
<summary><b>Q: Why are my inserts taking >10ms each?</b></summary>

**A:** Almost always environmental issues:

**Root causes (in order of likelihood):**

1. **iCloud/OneDrive/Dropbox sync** (90% of cases)
   - Solution: Move DB to `~/Local/vectorbench-db/`

2. **Network-attached storage**
   - Solution: Use local SSD

3. **Slow disk I/O**
   - Check: `sudo fs_usage -f filesys | grep kb.db`
   - Solution: Upgrade storage or reduce sync load

4. **Insufficient disk space**
   - Check: `df -h`
   - Solution: Free up space (< 10% free triggers slowdowns)

**Not a VectorLiteDB bug.** The library uses standard SQLite with synchronous writes for durability.
</details>

---

## Testing Decision Matrix

Use this table to understand what each test tells you about your system:

| Test | Question Answered | Good Result | Bad Result | Next Steps |
|:-----|:------------------|:------------|:-----------|:-----------|
| **Accuracy** | Are results correct? | Perfect Match | Mismatch Detected | Update library or rebuild DB |
| **Performance** | Is it fast enough? | Green/Blue status | Red status | Profile queries, check environment |
| **Benchmark** | What are the limits? | Search < 100ms | Search > 300ms | Reduce data or migrate to ANN |
| **Scale** | How does it grow? | Linear curve | Steep/flat curve | Investigate bottlenecks |
| **Crash Test** | Is data durable? | ✅ PASS | ❌ FAIL | Enable backups, check storage |

---


## Recommended Workflow

### Daily Development
```
1. Upload new documents
2. Run quick search tests
3. Monitor performance metrics
4. Check status indicator
```

### Before Deployment
```
1. Run full accuracy verification
2. Execute standard scale test
3. Verify P95 < 100ms
4. Run crash recovery test
5. Export results for documentation
```

### Troubleshooting
```
1. Check performance status
2. Run benchmark with multiple sizes
3. Execute scale test
4. Verify environment (iCloud, storage)
5. Check logs for errors
```

---

## Key Takeaways

### ✅ Trust but Verify

Run parity checks regularly. **Perfect Match** = mathematically correct results.

### ⚡ Aim for Green

Target P95 < 50ms for excellent UX. Yellow/Red status = investigate immediately.

### 📈 Expect Linear Scaling

Brute-force is O(N). When the curve steepens, it's time to consider ANN solutions.

### ⚠️ Watch for Environmental Issues

Slow inserts (>10ms) = cloud sync or network storage. Fix the environment, not the code.

### 🎯 Know Your Limits

VectorBench excels at 10K-100K vectors. Beyond that, migrate to purpose-built vector databases.

---

**Ready to dive deeper?** Start with Experiment 1 at http://localhost:8000 or explore the [testing framework](TESTING.md).
