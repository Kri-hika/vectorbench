import os, time, csv
import numpy as np
from vectorlitedb import VectorLiteDB

OUT = "latency_sweep.csv"
SIZES = [1000, 5000, 10000, 25000, 50000]  # adjust to taste
D = 384  # Match the embedding dimension used in the app
K = 5

def run_latency_sweep():
    """Run performance sweep across different database sizes"""
    print(f"Running latency sweep with sizes: {SIZES}")
    print(f"Vector dimension: {D}, Top-K: {K}")
    print(f"Output file: {OUT}")
    
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["N", "avg_insert_ms", "search_ms", "file_MB", "total_insert_time_s"])
        
        for N in SIZES:
            print(f"\nTesting N={N}...")
            path = f"bench_{N}.db"
            
            # Clean up any existing file
            if os.path.exists(path): 
                os.remove(path)
            
            # Create database
            db = VectorLiteDB(path, dimension=D, distance_metric="cosine")
            
            # Generate random vectors
            X = np.random.randn(N, D).astype("float32")
            
            # Measure insert performance
            print(f"  Inserting {N} vectors...")
            t0 = time.time()
            for i in range(N):
                db.insert(f"v{i}", X[i].tolist(), {"i": i, "batch": N})
            total_insert_time = time.time() - t0
            ins_ms = 1000 * total_insert_time / N
            
            # Measure search performance
            print(f"  Searching...")
            q = np.random.randn(D).astype("float32").tolist()
            t1 = time.time()
            results = db.search(q, top_k=K)
            search_ms = 1000 * (time.time() - t1)
            
            # Get file size
            file_mb = os.path.getsize(path) / 1e6
            
            # Write results
            w.writerow([N, round(ins_ms, 3), round(search_ms, 3), round(file_mb, 2), round(total_insert_time, 2)])
            print(f"  Results: insert={ins_ms:.3f}ms/vec, search={search_ms:.3f}ms, file={file_mb:.2f}MB")
            
            # Verify results are reasonable
            assert len(results) <= K, f"Too many results: {len(results)}"
            assert all('similarity' in r for r in results), "Missing similarity scores"
            
            # Clean up
            del db
            os.remove(path)
    
    print(f"\nLatency sweep complete! Results saved to {OUT}")
    print("\nTo analyze results:")
    print("1. Open the CSV in Excel/Sheets")
    print("2. Plot N vs search_ms to see linear scaling")
    print("3. Plot N vs file_MB to see storage growth")
    print("4. Plot N vs avg_insert_ms to check insert performance")

def run_metric_comparison():
    """Compare performance across different distance metrics"""
    print("\n" + "="*50)
    print("Running metric comparison...")
    
    N = 10000  # Fixed size for metric comparison
    D = 64     # Smaller dimension for faster testing
    K = 10
    
    metrics = ["cosine", "dot", "l2"]
    results = {}
    
    for metric in metrics:
        print(f"\nTesting {metric} metric...")
        path = f"metric_bench_{metric}.db"
        
        if os.path.exists(path):
            os.remove(path)
        
        db = VectorLiteDB(path, dimension=D, distance_metric=metric)
        X = np.random.randn(N, D).astype("float32")
        
        # Insert
        t0 = time.time()
        for i in range(N):
            db.insert(f"v{i}", X[i].tolist(), {"i": i})
        insert_time = time.time() - t0
        
        # Search
        q = np.random.randn(D).astype("float32").tolist()
        t1 = time.time()
        search_results = db.search(q, top_k=K)
        search_time = time.time() - t1
        
        results[metric] = {
            'insert_ms': 1000 * insert_time / N,
            'search_ms': 1000 * search_time,
            'file_mb': os.path.getsize(path) / 1e6
        }
        
        print(f"  {metric}: insert={results[metric]['insert_ms']:.3f}ms/vec, "
              f"search={results[metric]['search_ms']:.3f}ms, "
              f"file={results[metric]['file_mb']:.2f}MB")
        
        del db
        os.remove(path)
    
    # Print comparison
    print(f"\nMetric Performance Comparison (N={N}, D={D}):")
    print("Metric    | Insert (ms/vec) | Search (ms) | File (MB)")
    print("-" * 55)
    for metric in metrics:
        r = results[metric]
        print(f"{metric:8} | {r['insert_ms']:13.3f} | {r['search_ms']:10.3f} | {r['file_mb']:8.2f}")

def run_dimension_sweep():
    """Test performance across different vector dimensions"""
    print("\n" + "="*50)
    print("Running dimension sweep...")
    
    N = 5000   # Fixed size
    DIMS = [32, 64, 128, 256, 384, 512]
    K = 5
    
    print("Dimension | Insert (ms/vec) | Search (ms) | File (MB)")
    print("-" * 55)
    
    for D in DIMS:
        path = f"dim_bench_{D}.db"
        
        if os.path.exists(path):
            os.remove(path)
        
        db = VectorLiteDB(path, dimension=D, distance_metric="cosine")
        X = np.random.randn(N, D).astype("float32")
        
        # Insert
        t0 = time.time()
        for i in range(N):
            db.insert(f"v{i}", X[i].tolist(), {"i": i})
        insert_time = time.time() - t0
        
        # Search
        q = np.random.randn(D).astype("float32").tolist()
        t1 = time.time()
        search_results = db.search(q, top_k=K)
        search_time = time.time() - t1
        
        file_mb = os.path.getsize(path) / 1e6
        
        print(f"{D:9} | {1000*insert_time/N:13.3f} | {1000*search_time:10.3f} | {file_mb:8.2f}")
        
        del db
        os.remove(path)

def run_topk_sweep():
    """Test search performance across different top-k values"""
    print("\n" + "="*50)
    print("Running top-k sweep...")
    
    N = 10000
    D = 128
    TOP_K_VALUES = [1, 5, 10, 20, 50, 100]
    
    path = "topk_bench.db"
    if os.path.exists(path):
        os.remove(path)
    
    db = VectorLiteDB(path, dimension=D, distance_metric="cosine")
    X = np.random.randn(N, D).astype("float32")
    
    # Insert all vectors
    print("Inserting vectors...")
    for i in range(N):
        db.insert(f"v{i}", X[i].tolist(), {"i": i})
    
    q = np.random.randn(D).astype("float32").tolist()
    
    print("Top-K | Search (ms) | Results")
    print("-" * 30)
    
    for k in TOP_K_VALUES:
        t0 = time.time()
        results = db.search(q, top_k=k)
        search_time = time.time() - t0
        
        print(f"{k:5} | {1000*search_time:10.3f} | {len(results):7}")
    
    del db
    os.remove(path)

if __name__ == "__main__":
    print("VectorLiteDB Performance Analysis")
    print("=" * 50)
    
    # Run all performance tests
    run_latency_sweep()
    run_metric_comparison()
    run_dimension_sweep()
    run_topk_sweep()
    
    print("\n" + "="*50)
    print("Performance analysis complete!")
    print("\nKey insights to look for:")
    print("1. Linear scaling: search time should scale roughly O(N)")
    print("2. Dimension impact: higher dimensions = slower search")
    print("3. Metric differences: cosine vs dot vs L2 may have different performance")
    print("4. Top-K impact: larger K values should take longer")
    print("5. File size: should grow roughly linearly with N and D")
