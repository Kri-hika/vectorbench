import threading, time, os
import numpy as np
from vectorlitedb import VectorLiteDB

DB = "conc.db"
D = 64

def writer_thread(db, vectors, thread_id, results):
    """Writer thread that inserts vectors"""
    try:
        for i, v in enumerate(vectors):
            db.insert(f"id_{thread_id}_{i}", v.tolist(), {"thread": thread_id, "index": i})
            if i % 1000 == 0:
                time.sleep(0.05)  # Brief pause every 1000 inserts
        results[f"writer_{thread_id}"] = "SUCCESS"
    except Exception as e:
        results[f"writer_{thread_id}"] = f"ERROR: {e}"

def reader_thread(db_path, thread_id, results, num_reads=100):
    """Reader thread that performs searches"""
    try:
        db = VectorLiteDB(db_path, dimension=D)
        for i in range(num_reads):
            q = np.random.randn(D).tolist()
            try:
                search_results = db.search(q, top_k=3)
                assert isinstance(search_results, list)
            except Exception as e:
                results[f"reader_{thread_id}_error_{i}"] = str(e)
            time.sleep(0.02)  # Brief pause between reads
        results[f"reader_{thread_id}"] = "SUCCESS"
    except Exception as e:
        results[f"reader_{thread_id}"] = f"ERROR: {e}"

def test_single_writer_multiple_readers():
    """Test one writer with multiple readers"""
    print("Testing single writer with multiple readers...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    # Create writer database
    writer_db = VectorLiteDB(DB, dimension=D, distance_metric="cosine")
    X = np.random.randn(8000, D).astype("float32")
    
    results = {}
    threads = []
    
    # Start writer thread
    writer_thread_obj = threading.Thread(
        target=writer_thread, 
        args=(writer_db, X, "main", results),
        daemon=True
    )
    threads.append(writer_thread_obj)
    
    # Start reader threads
    for i in range(3):
        reader_thread_obj = threading.Thread(
            target=reader_thread,
            args=(DB, f"reader_{i}", results, 50),
            daemon=True
        )
        threads.append(reader_thread_obj)
    
    # Start all threads
    for t in threads:
        t.start()
    
    # Wait for all threads to complete
    for t in threads:
        t.join(timeout=30)  # 30 second timeout
    
    # Check results
    print("Results:")
    for key, value in results.items():
        print(f"  {key}: {value}")
    
    # Check final database state
    final_len = len(writer_db)
    print(f"Final database length: {final_len}")
    
    # Try a final search to ensure DB is still functional
    try:
        final_search = writer_db.search([1.0] * D, top_k=5)
        print(f"Final search returned {len(final_search)} results")
    except Exception as e:
        print(f"Final search failed: {e}")
    
    # Clean up
    del writer_db
    if os.path.exists(DB):
        os.remove(DB)
    
    return results

def test_multiple_writers():
    """Test multiple writers (this might fail - good to know!)"""
    print("\nTesting multiple writers...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    results = {}
    threads = []
    
    # Create separate writer threads
    for writer_id in range(3):
        X = np.random.randn(2000, D).astype("float32")
        writer_thread_obj = threading.Thread(
            target=writer_thread,
            args=(None, X, f"writer_{writer_id}", results),  # Will create own DB connection
            daemon=True
        )
        threads.append(writer_thread_obj)
    
    # Start all writer threads
    for t in threads:
        t.start()
    
    # Wait for completion
    for t in threads:
        t.join(timeout=20)
    
    print("Multiple writer results:")
    for key, value in results.items():
        print(f"  {key}: {value}")
    
    # Check if any writers succeeded
    success_count = sum(1 for v in results.values() if v == "SUCCESS")
    print(f"Successful writers: {success_count}/3")
    
    # Clean up
    if os.path.exists(DB):
        os.remove(DB)
    
    return results

def test_reader_during_writer():
    """Test readers while writer is actively writing"""
    print("\nTesting readers during active writing...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    writer_db = VectorLiteDB(DB, dimension=D, distance_metric="cosine")
    results = {}
    threads = []
    
    # Writer that does batch inserts
    def batch_writer():
        try:
            for batch in range(10):
                batch_vectors = np.random.randn(500, D).astype("float32")
                for i, v in enumerate(batch_vectors):
                    writer_db.insert(f"batch_{batch}_{i}", v.tolist(), {"batch": batch})
                time.sleep(0.1)  # Pause between batches
            results["batch_writer"] = "SUCCESS"
        except Exception as e:
            results["batch_writer"] = f"ERROR: {e}"
    
    # Reader that tries to read during writing
    def active_reader():
        try:
            db = VectorLiteDB(DB, dimension=D)
            for i in range(20):
                q = np.random.randn(D).tolist()
                try:
                    search_results = db.search(q, top_k=5)
                    results[f"read_success_{i}"] = len(search_results)
                except Exception as e:
                    results[f"read_error_{i}"] = str(e)
                time.sleep(0.05)
            results["active_reader"] = "SUCCESS"
        except Exception as e:
            results["active_reader"] = f"ERROR: {e}"
    
    # Start threads
    writer_thread_obj = threading.Thread(target=batch_writer, daemon=True)
    reader_thread_obj = threading.Thread(target=active_reader, daemon=True)
    
    threads = [writer_thread_obj, reader_thread_obj]
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join(timeout=15)
    
    print("Active reader results:")
    for key, value in results.items():
        if "read_success" in key:
            print(f"  {key}: {value} results")
        elif "read_error" in key:
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: {value}")
    
    # Clean up
    del writer_db
    if os.path.exists(DB):
        os.remove(DB)
    
    return results

def test_database_locking_behavior():
    """Test what happens when trying to open the same DB multiple times"""
    print("\nTesting database locking behavior...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    # Create initial DB
    db1 = VectorLiteDB(DB, dimension=D, distance_metric="cosine")
    db1.insert("test", [1.0] * D, {"test": True})
    
    results = {}
    
    # Try to open the same DB file again
    try:
        db2 = VectorLiteDB(DB, dimension=D)
        results["second_connection"] = "SUCCESS"
        
        # Try to read from second connection
        try:
            vector, metadata = db2.get("test")
            results["second_read"] = "SUCCESS"
        except Exception as e:
            results["second_read"] = f"ERROR: {e}"
        
        # Try to write from second connection
        try:
            db2.insert("test2", [2.0] * D, {"test": True})
            results["second_write"] = "SUCCESS"
        except Exception as e:
            results["second_write"] = f"ERROR: {e}"
        
        del db2
        
    except Exception as e:
        results["second_connection"] = f"ERROR: {e}"
    
    # Try to read from first connection
    try:
        vector, metadata = db1.get("test")
        results["first_read"] = "SUCCESS"
    except Exception as e:
        results["first_read"] = f"ERROR: {e}"
    
    print("Database locking results:")
    for key, value in results.items():
        print(f"  {key}: {value}")
    
    # Clean up
    del db1
    if os.path.exists(DB):
        os.remove(DB)
    
    return results

def test_stress_concurrency():
    """Stress test with many concurrent operations"""
    print("\nRunning stress concurrency test...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    results = {}
    threads = []
    
    # Multiple readers
    for i in range(5):
        reader_thread_obj = threading.Thread(
            target=reader_thread,
            args=(DB, f"stress_reader_{i}", results, 30),
            daemon=True
        )
        threads.append(reader_thread_obj)
    
    # One writer
    X = np.random.randn(3000, D).astype("float32")
    writer_thread_obj = threading.Thread(
        target=writer_thread,
        args=(None, X, "stress_writer", results),
        daemon=True
    )
    threads.append(writer_thread_obj)
    
    # Start all threads
    for t in threads:
        t.start()
    
    # Wait for completion
    for t in threads:
        t.join(timeout=25)
    
    # Count successes
    success_count = sum(1 for v in results.values() if v == "SUCCESS")
    error_count = sum(1 for v in results.values() if "ERROR" in str(v))
    
    print(f"Stress test results: {success_count} successes, {error_count} errors")
    
    # Clean up
    if os.path.exists(DB):
        os.remove(DB)
    
    return results

if __name__ == "__main__":
    print("VectorLiteDB Concurrency Testing")
    print("=" * 50)
    
    # Run all concurrency tests
    test_single_writer_multiple_readers()
    test_multiple_writers()
    test_reader_during_writer()
    test_database_locking_behavior()
    test_stress_concurrency()
    
    print("\n" + "="*50)
    print("Concurrency testing complete!")
    print("\nKey findings to document:")
    print("1. Can multiple readers access the DB simultaneously?")
    print("2. Can readers access the DB while a writer is active?")
    print("3. What happens with multiple writers?")
    print("4. Does the DB support multiple connections to the same file?")
    print("5. What are the failure modes under stress?")
    print("\nUse these results to determine the appropriate concurrency model for your application.")
