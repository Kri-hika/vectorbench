import os, json, random, string
from vectorlitedb import VectorLiteDB

DB = "bigmeta.db"
D = 32

def randtxt(n):
    """Generate random text of length n"""
    return "".join(random.choices(string.ascii_letters + " ", k=n))

def test_big_metadata_basic():
    """Test basic functionality with large metadata"""
    print("Testing basic big metadata functionality...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    db = VectorLiteDB(DB, dimension=D)
    
    # Test with moderately large metadata
    for i in range(100):
        vec = [0.0] * D
        vec[i % D] = 1.0
        meta = {"i": i, "blob": randtxt(1000)}  # 1KB metadata
        db.insert(f"id{i}", vec, meta)
    
    print(f"Inserted 100 vectors with 1KB metadata each")
    print(f"DB length: {len(db)}")
    print(f"File size: {os.path.getsize(DB)/1e6:.2f} MB")
    
    # Test search with large metadata
    results = db.search([1] + [0] * (D-1), top_k=3)
    print(f"Search returned {len(results)} results")
    
    # Verify metadata is intact
    for result in results:
        assert "blob" in result["metadata"], "Large metadata blob missing"
        assert len(result["metadata"]["blob"]) == 1000, "Metadata blob size incorrect"
    
    # Clean up
    del db
    os.remove(DB)

def test_very_large_metadata():
    """Test with very large metadata blobs"""
    print("\nTesting very large metadata blobs...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    db = VectorLiteDB(DB, dimension=D)
    
    # Test with very large metadata (10KB per item)
    for i in range(50):
        vec = [0.0] * D
        vec[i % D] = 1.0
        meta = {
            "i": i,
            "large_blob": randtxt(10000),  # 10KB
            "json_data": {
                "nested": {
                    "deep": {
                        "structure": [j for j in range(100)],
                        "text": randtxt(1000)
                    }
                }
            }
        }
        db.insert(f"large_{i}", vec, meta)
    
    print(f"Inserted 50 vectors with ~10KB metadata each")
    print(f"DB length: {len(db)}")
    print(f"File size: {os.path.getsize(DB)/1e6:.2f} MB")
    
    # Test search
    results = db.search([1] + [0] * (D-1), top_k=5)
    print(f"Search returned {len(results)} results")
    
    # Verify large metadata is intact
    for result in results:
        meta = result["metadata"]
        assert len(meta["large_blob"]) == 10000, "Large blob size incorrect"
        assert len(meta["json_data"]["nested"]["deep"]["structure"]) == 100, "Nested structure incorrect"
    
    # Clean up
    del db
    os.remove(DB)

def test_metadata_size_limits():
    """Test what happens with extremely large metadata"""
    print("\nTesting metadata size limits...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    db = VectorLiteDB(DB, dimension=D)
    
    # Test progressively larger metadata
    sizes = [1000, 10000, 100000, 500000]  # 1KB, 10KB, 100KB, 500KB
    
    for size in sizes:
        try:
            vec = [1.0] * D
            meta = {"size": size, "blob": randtxt(size)}
            db.insert(f"size_{size}", vec, meta)
            print(f"Successfully inserted {size} bytes metadata")
        except Exception as e:
            print(f"Failed to insert {size} bytes metadata: {e}")
            break
    
    print(f"Final DB length: {len(db)}")
    print(f"Final file size: {os.path.getsize(DB)/1e6:.2f} MB")
    
    # Test search with largest successful metadata
    results = db.search([1.0] * D, top_k=5)
    print(f"Search returned {len(results)} results")
    
    # Clean up
    del db
    os.remove(DB)

def test_unicode_metadata():
    """Test with large Unicode metadata"""
    print("\nTesting large Unicode metadata...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    db = VectorLiteDB(DB, dimension=D)
    
    # Test with various Unicode content
    unicode_samples = [
        "中文" * 1000,  # Chinese characters
        "🚀🎉🌟💫⭐" * 200,  # Emojis
        "café naïve résumé" * 100,  # Accented characters
        "αβγδεζηθικλμνξοπρστυφχψω" * 50,  # Greek letters
    ]
    
    for i, unicode_text in enumerate(unicode_samples):
        vec = [0.0] * D
        vec[i] = 1.0
        meta = {
            "i": i,
            "unicode_text": unicode_text,
            "length": len(unicode_text),
            "bytes": len(unicode_text.encode('utf-8'))
        }
        db.insert(f"unicode_{i}", vec, meta)
    
    print(f"Inserted {len(unicode_samples)} vectors with Unicode metadata")
    print(f"DB length: {len(db)}")
    print(f"File size: {os.path.getsize(DB)/1e6:.2f} MB")
    
    # Test search
    results = db.search([1] + [0] * (D-1), top_k=3)
    print(f"Search returned {len(results)} results")
    
    # Verify Unicode metadata is intact
    for result in results:
        meta = result["metadata"]
        assert "unicode_text" in meta, "Unicode text missing"
        assert meta["length"] == len(meta["unicode_text"]), "Unicode length mismatch"
    
    # Clean up
    del db
    os.remove(DB)

def test_metadata_filtering_performance():
    """Test filtering performance with large metadata"""
    print("\nTesting metadata filtering performance...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    db = VectorLiteDB(DB, dimension=D)
    
    # Insert data with large metadata and various filterable fields
    categories = ["A", "B", "C", "D", "E"]
    priorities = [1, 2, 3, 4, 5]
    
    for i in range(1000):
        vec = [random.random() for _ in range(D)]
        meta = {
            "id": i,
            "category": random.choice(categories),
            "priority": random.choice(priorities),
            "large_blob": randtxt(5000),  # 5KB blob
            "nested": {
                "level1": {
                    "level2": {
                        "value": random.randint(0, 100),
                        "text": randtxt(1000)
                    }
                }
            }
        }
        db.insert(f"item_{i}", vec, meta)
    
    print(f"Inserted 1000 vectors with 5KB metadata each")
    print(f"DB length: {len(db)}")
    print(f"File size: {os.path.getsize(DB)/1e6:.2f} MB")
    
    # Test various filter complexities
    import time
    
    q = [0.5] * D
    
    # Simple filter
    f1 = lambda m: m.get("category") == "A"
    t0 = time.time()
    r1 = db.search(q, top_k=50, filter=f1)
    t1 = time.time()
    print(f"Simple filter: {len(r1)} results in {1000*(t1-t0):.3f}ms")
    
    # Complex filter with nested access
    f2 = lambda m: (m.get("category") in ["A", "B"] and 
                   m.get("priority", 0) >= 3 and 
                   m.get("nested", {}).get("level1", {}).get("level2", {}).get("value", 0) > 50)
    t0 = time.time()
    r2 = db.search(q, top_k=50, filter=f2)
    t1 = time.time()
    print(f"Complex nested filter: {len(r2)} results in {1000*(t1-t0):.3f}ms")
    
    # Verify filter results
    for result in r1:
        assert result["metadata"]["category"] == "A"
    
    for result in r2:
        meta = result["metadata"]
        assert meta["category"] in ["A", "B"]
        assert meta["priority"] >= 3
        assert meta["nested"]["level1"]["level2"]["value"] > 50
    
    # Clean up
    del db
    os.remove(DB)

def test_metadata_memory_usage():
    """Test memory usage with large metadata"""
    print("\nTesting memory usage with large metadata...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    # Try to estimate memory usage
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    db = VectorLiteDB(DB, dimension=D)
    
    # Insert many vectors with large metadata
    for i in range(2000):
        vec = [0.0] * D
        vec[i % D] = 1.0
        meta = {"i": i, "blob": randtxt(4000)}  # 4KB per item
        db.insert(f"id{i}", vec, meta)
        
        if i % 500 == 0:
            current_memory = process.memory_info().rss / 1024 / 1024
            print(f"After {i} inserts: {current_memory:.1f} MB (delta: {current_memory-initial_memory:.1f} MB)")
    
    final_memory = process.memory_info().rss / 1024 / 1024
    print(f"Final memory usage: {final_memory:.1f} MB (delta: {final_memory-initial_memory:.1f} MB)")
    print(f"DB length: {len(db)}")
    print(f"File size: {os.path.getsize(DB)/1e6:.2f} MB")
    
    # Test search to ensure functionality
    results = db.search([1] + [0] * (D-1), top_k=5)
    print(f"Search returned {len(results)} results")
    
    # Clean up
    del db
    os.remove(DB)

def test_metadata_corruption_resilience():
    """Test resilience to metadata corruption scenarios"""
    print("\nTesting metadata corruption resilience...")
    
    if os.path.exists(DB):
        os.remove(DB)
    
    db = VectorLiteDB(DB, dimension=D)
    
    # Insert data with various metadata types that could cause issues
    problematic_metadata = [
        {"null_value": None, "empty_string": "", "zero": 0, "false": False},
        {"very_long_key": "x" * 1000, "value": "y" * 1000},
        {"nested_nulls": {"a": None, "b": {"c": None, "d": "value"}}},
        {"special_chars": "!@#$%^&*()_+-=[]{}|;':\",./<>?" * 10},
        {"unicode_mix": "Hello 世界 🌍 café naïve"},
    ]
    
    for i, meta in enumerate(problematic_metadata):
        vec = [0.0] * D
        vec[i] = 1.0
        db.insert(f"problem_{i}", vec, meta)
    
    print(f"Inserted {len(problematic_metadata)} vectors with problematic metadata")
    
    # Test that all data can be retrieved
    for i in range(len(problematic_metadata)):
        try:
            vector, metadata = db.get(f"problem_{i}")
            assert vector == [0.0] * D
            assert metadata == problematic_metadata[i]
        except Exception as e:
            print(f"Failed to retrieve problem_{i}: {e}")
    
    # Test search
    results = db.search([1] + [0] * (D-1), top_k=5)
    print(f"Search returned {len(results)} results")
    
    # Clean up
    del db
    os.remove(DB)

if __name__ == "__main__":
    print("VectorLiteDB Big Metadata Testing")
    print("=" * 50)
    
    # Run all big metadata tests
    test_big_metadata_basic()
    test_very_large_metadata()
    test_metadata_size_limits()
    test_unicode_metadata()
    test_metadata_filtering_performance()
    test_metadata_memory_usage()
    test_metadata_corruption_resilience()
    
    print("\n" + "="*50)
    print("Big metadata testing complete!")
    print("\nKey findings:")
    print("1. Maximum metadata size that can be stored")
    print("2. Performance impact of large metadata on search")
    print("3. Memory usage patterns with large metadata")
    print("4. Unicode and special character handling")
    print("5. Filtering performance with large metadata")
    print("6. Resilience to problematic metadata values")
