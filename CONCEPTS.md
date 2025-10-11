# Understanding VectorBench

Learn how vector search works by running experiments and seeing real results.

---

## Core Questions

### Is VectorLiteDB giving correct results?

When you search for *"machine learning"*, you want the **most relevant documents**, not random ones. We test this by comparing against NumPy's brute force implementation (the *"gold standard"*).

<br>

### How fast is it?

Search latency matters. **Sub-100ms** feels instant. **Over 500ms** feels slow. We measure **P50/P95** to catch both typical and worst-case performance.

<br>

### What happens when things break?

If the app crashes during document ingestion, do you lose data? **Crash tests** verify durability.

<br>

### Can it handle real data?

Real documents have weird characters, large files, and edge cases. **Stress tests** verify robustness.

---

## Interface Layout

```
┌─────────────────────┬────────────────────────┐
│ LEFT PANEL          │ RIGHT PANEL            │
├─────────────────────┼────────────────────────┤
│ 📤 Upload           │ 🔍 Search (sticky)     │
│ 📊 Performance      │ 🕐 Recent Searches     │
│ ⚡ Quick Actions     │ 📄 Results             │
│ 📈 Latency Chart    │                        │
│ 🧪 Advanced Tests   │                        │
└─────────────────────┴────────────────────────┘
```

<br>

### Quick Actions

*One-click testing with sensible defaults:*

- **⚡ Benchmark** → 500 vectors
- **✓ Accuracy** → Verify correctness
- **🔄 Health** → System status
- **📊 Scale** → Quick scaling test

<br>

### Advanced Tests

*Customizable options for deeper analysis:*

- **Quick Benchmark** → Choose *100/500/1K/2K vectors*
- **Scale Test** → *Quick/Standard/Thorough* profiles
- **Accuracy Verification** → Test with *5/10/20 results*
- **System Health** → Detailed diagnostics

<br>

### Header Actions

- **🧪 Run All Tests** → Full diagnostic suite
- **📊 Export** → Copy report to clipboard

<br>

### Performance Metrics

*Auto-refreshes every 5 seconds:*

| Metric | Description |
|--------|-------------|
| **Indexed files** | Number of files in database |
| **Total queries** | Searches executed |
| **P95 latency** | *95th percentile response time* |
| **Status** | *Color-coded performance indicator* |

---

## Hands-On Experiments

### Experiment 1: Verify Accuracy

**Question**: *Are my search results correct?*

**Steps**:
1. Open http://localhost:8000
2. Click **"✓ Accuracy"** in *Quick Actions*
3. Wait **1-3 seconds**

<br>

**Expected output**:
```
✅ Accuracy Verified

✅ Perfect Match!
VectorLiteDB results are identical to the gold-standard
NumPy implementation. Your search results are 
mathematically correct! 🎉

Test Details:
• Compared top 5 search results
• Baseline: NumPy ✓
• VectorLiteDB: ✓
```

<br>

**What it means**:
- ✅ **"Perfect Match!"** → VectorLiteDB works correctly
- ❌ **"Mismatch Detected"** → Algorithm issue

> Test compares **1000 random vectors** against NumPy. If this fails, your search results are *mathematically wrong*.

---

### Experiment 2: Check Performance

**Question**: *How fast is search?*

**Steps**:
1. Look at **Performance** section *(left panel)*
2. Metrics auto-refresh every **5s**
3. *Optional*: Click **"🔄 Health"** for details

<br>

#### **Status Colors**:

| Color | Latency | Meaning |
|-------|---------|---------|
| 🟢 **Green** | *< 50ms* | **Lightning fast** |
| 🔵 **Blue** | *50-100ms* | **Production ready** |
| 🟡 **Yellow** | *100-300ms* | *Noticeable delay* |
| 🔴 **Red** | *> 300ms* | **Needs optimization** |

<br>

**Metrics explained**:
- **Indexed**: Files in database
- **Queries**: Total searches run
- **Latency (P95)**: *95% of searches complete within this time*
- **Status**: Human-readable assessment

> Users expect results in under **100ms**. Color coding gives instant feedback.

---

### Experiment 3: Find Performance Limits

**Question**: *How many documents before it gets too slow?*

**Steps**:
1. Click **"⚡ Benchmark"** *(tests 500 vectors)*
2. **Or** expand **Advanced Tests** → select count → **Run Benchmark**

<br>

#### **Test Sizes**:

| Size | Duration | Use Case |
|------|----------|----------|
| **100** | *~2s* | Fast check |
| **500** | *~10s* | **Recommended** |
| **1,000** | *~30s* | Thorough |
| **2,000** | *~1min* | Advanced |

<br>

**Expected results**:
```
✓ Quick Benchmark Results

Database Size: 500 vectors
Insert Speed: 0.8ms per vector
Search Time: 45.2ms
File Size: 12.3 MB

Good Performance: Search completed in 45.2ms
```

<br>

**Metrics**:
- **Insert Speed**: Time to add each document *(< 5ms is good)*
- **Search Time**: Query latency *(< 100ms is excellent)*
- **File Size**: Storage requirements

<br>

#### **Warning Signs**:
```
⚠️ Slow inserts detected (15.2ms avg)

This may indicate:
• Project on iCloud or network drive
• Slow disk I/O
• Move database to local storage
```

> Slow inserts *(> 10ms)* almost always mean **iCloud sync**. Fix by moving database to `~/Local/vectorbench-db/`

---

### Experiment 4: Test Scaling

**Question**: *What happens when I add 10x more documents?*

**Steps**:
1. Expand **Advanced Tests**
2. Find **"📊 Scale Test"**
3. Select profile

<br>

#### **Profiles**:

| Profile | Sizes | Duration |
|---------|-------|----------|
| **Quick** | *100, 250, 500* | ~20s |
| **Standard** | *500, 1K, 2K* | ~1min |
| **Thorough** | *1K, 2.5K, 5K* | ~3min |

<br>

**Output**: *Line graph showing search time vs database size*

```
Search Time (ms)
     ↑
 100 |                    •
  80 |              •
  60 |        •
  40 |  •
   0 └────────────────────→
     100  250  500  1K
```

<br>

**What to look for**:
- **Linear growth**: *Normal for brute-force*
- **Steep curve**: *Approaching scale limits*
- **Flat curve**: *Small dataset or caching*

> This tells you **when to migrate** to a more sophisticated database.

---

### Experiment 5: Test Durability

**Question**: *Will I lose data if something crashes?*

**Steps**:
```bash
python -c "from tests.test_persistence_crash import test_normal_persistence; test_normal_persistence()"
```

<br>

**Expected**: `✅ PASS`

**If it fails**: You could lose data in a crash. Implement **backups** or switch to **WAL mode**.

---

## Technical Terms Explained

### Parity Check

Compare VectorLiteDB to NumPy's *brute-force implementation*. Both search **1000 random vectors**. If top results match, accuracy is verified.

<br>

### Latency

Time from search request to results. Measured in **milliseconds (ms)**. *1000ms = 1 second*.

<br>

### P50/P95

- **P50** *(median)*: Half of searches are this fast or faster
- **P95** *(95th percentile)*: 95% of searches are this fast or faster

> We show **P95** because it catches slow outliers that P50 might hide. *P95 should be < 2x P50* for stable performance.

<br>

### Brute Force

Check **every document** to find best matches. Slow but **100% correct**. VectorLiteDB should match brute force results exactly.

**Alternative**: *ANN (Approximate Nearest Neighbor)* - faster but slightly less accurate.

<br>

### Status

*Human-readable performance assessment:*

| Icon | Range | Meaning |
|------|-------|---------|
| 🟢 | *< 50ms* | **Lightning fast** |
| 🔵 | *50-100ms* | **Production ready** |
| 🟡 | *100-300ms* | *Acceptable* |
| 🔴 | *> 300ms* | **Needs optimization** |

---

## Common Questions

### Why does parity check show different numbers sometimes?

When documents have very similar scores *(0.8523 vs 0.8522)*, order might vary due to **floating-point precision**. **"Perfect Match!"** means results are correct.

<br>

### My search is slow - what now?

1. Check **Status** card *(yellow/red = investigate)*
2. Look at **Indexed** count *(more files = slower)*
3. Run **Scale Test** to see performance curve
4. If consistently **> 300ms**, consider *Chroma/Qdrant/FAISS*

<br>

### File size growing fast - is this normal?

**Yes**. Each chunk *(384-dim vector + metadata)* = ~2-5 KB. Expect **~10 MB per 1,000 vectors**.

<br>

### What if crash test fails?

**Serious**. Means potential data loss:

1. Check **VectorLiteDB version**
2. Ensure database isn't on *unreliable storage*
3. Implement **backups**
4. Consider **WAL mode** for SQLite

<br>

### Why Quick Actions AND Advanced Tests?

- **Quick Actions**: *One-click with defaults* (quick checks)
- **Advanced Tests**: *Customizable* (deep analysis)

<br>

### What does "Run All Tests" do?

Executes complete diagnostic suite:

1. **System Health Check**
2. **Quick Benchmark** *(500 vectors)*
3. **Accuracy Verification**
4. **Scale Test** *(quick profile)*

Shows **live progress**. Results exportable to clipboard.

<br>

### Benchmark shows slow inserts (>10ms) - why?

Almost always:

1. **iCloud Drive sync** *(move project out of ~/Documents)*
2. **Network storage** *(use local SSD)*
3. **Slow disk** *(check disk performance)*

**Solution**: Move database to `~/Local/vectorbench-db/`

---

## Test Summary

| Test | Measures | Good Result | Bad Result | Action |
|------|----------|-------------|------------|--------|
| **Accuracy** | Correctness | *Perfect Match!* | *Mismatch* | Check version |
| **Performance** | Speed | *Good/Excellent* | *Slow* | Optimize |
| **Benchmark** | Limits | *< 100ms* | *> 300ms* | Migrate |
| **Scale** | Scaling | *Linear* | *Steep* | Near limit |
| **Crash** | Durability | ✅ *PASS* | ❌ *FAIL* | Backup |

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **⌘K** | *Focus search* |
| **⌘↵** | *Execute search* |
| **⌘T** | **Run all tests** |
| **⌘E** | **Export results** |
| **Esc** | *Clear search* |

---

## Next Steps

1. **Add documents** via upload, watch metrics change
2. **Try different searches**, observe latency
3. **Run benchmarks** with different counts
4. **Compare** Scale Test profiles
5. **Test edge cases** *(long docs, special chars)*
6. **Export results**, track performance over time

---

## Key Takeaways

✅ **Green Status = Happy Users**  
*Aim for P95 < 100ms*

✅ **Perfect Match = Trust the Math**  
*Accuracy checks validate correctness*

✅ **Linear Scaling = Expected**  
*Brute force is O(N)*

⚠️ **Slow Inserts = Environment Issue**  
*Almost always iCloud/network*

📊 **Scale Test = Migration Signal**  
*Steep curve = consider alternatives*

---

> Use these experiments to **understand your system**, not just pass tests. The metrics help you make **informed decisions** about when to use VectorBench vs. more sophisticated databases.

**Ready to start?** Open http://localhost:8000 and click **"✓ Accuracy"** to verify your setup.
