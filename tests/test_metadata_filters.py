from vectorlitedb import VectorLiteDB
import tempfile, os

def test_complex_filters():
    """Test complex metadata filtering scenarios"""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        path = tf.name
    
    db = VectorLiteDB(path, dimension=4)
    
    # Insert test data with various metadata structures
    test_data = [
        ("a", [1, 0, 0, 0], {"type": "doc", "lang": "en", "tag": ["x", "y"], "len": 50}),
        ("b", [0, 1, 0, 0], {"type": "note", "lang": "fr", "tag": ["y"], "len": 10}),
        ("c", [0.9, 0.1, 0, 0], {"type": "doc", "lang": "en", "tag": [], "len": 200}),
        ("d", [0, 0, 1, 0], {"type": "image", "lang": "en", "tag": ["x", "z"], "len": 5}),
        ("e", [0.1, 0.9, 0, 0], {"type": "doc", "lang": "es", "tag": ["y", "z"], "len": 150}),
    ]
    
    for id_val, vector, metadata in test_data:
        db.insert(id_val, vector, metadata)
    
    q = [0.95, 0.05, 0, 0]
    
    # Test compound filter
    f1 = lambda m: m.get("type") == "doc" and m.get("lang") == "en" and m.get("len", 0) > 100
    r1 = db.search(q, top_k=10, filter=f1)
    assert {x["id"] for x in r1} == {"c"}, f"Compound filter failed: got {[x['id'] for x in r1]}"
    
    # Test list membership
    f2 = lambda m: "y" in (m.get("tag") or [])
    r2 = db.search(q, top_k=10, filter=f2)
    assert {x["id"] for x in r2} == {"a", "b", "e"}, f"List membership filter failed: got {[x['id'] for x in r2]}"
    
    # Test multiple list membership
    f3 = lambda m: "x" in (m.get("tag") or []) and "z" in (m.get("tag") or [])
    r3 = db.search(q, top_k=10, filter=f3)
    assert {x["id"] for x in r3} == {"d"}, f"Multiple list membership failed: got {[x['id'] for x in r3]}"
    
    # Test numeric range
    f4 = lambda m: 50 <= m.get("len", 0) <= 150
    r4 = db.search(q, top_k=10, filter=f4)
    assert {x["id"] for x in r4} == {"a", "e"}, f"Numeric range filter failed: got {[x['id'] for x in r4]}"
    
    # Test language filter
    f5 = lambda m: m.get("lang") in ["en", "es"]
    r5 = db.search(q, top_k=10, filter=f5)
    assert {x["id"] for x in r5} == {"a", "c", "d", "e"}, f"Language filter failed: got {[x['id'] for x in r5]}"
    
    os.remove(path)

def test_filter_with_none_values():
    """Test filtering with None/missing values"""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        path = tf.name
    
    db = VectorLiteDB(path, dimension=3)
    
    # Insert data with some missing fields
    test_data = [
        ("a", [1, 0, 0], {"type": "doc", "priority": 1}),
        ("b", [0, 1, 0], {"type": "note"}),  # missing priority
        ("c", [0, 0, 1], {"priority": 2}),   # missing type
        ("d", [0.5, 0.5, 0], {}),           # empty metadata
    ]
    
    for id_val, vector, metadata in test_data:
        db.insert(id_val, vector, metadata)
    
    q = [0.9, 0.1, 0]
    
    # Test filter that handles missing values
    f1 = lambda m: m.get("type") == "doc"
    r1 = db.search(q, top_k=10, filter=f1)
    assert {x["id"] for x in r1} == {"a"}, f"Type filter with missing values failed: got {[x['id'] for x in r1]}"
    
    # Test filter with default values
    f2 = lambda m: m.get("priority", 0) >= 1
    r2 = db.search(q, top_k=10, filter=f2)
    assert {x["id"] for x in r2} == {"a", "c"}, f"Priority filter with defaults failed: got {[x['id'] for x in r2]}"
    
    # Test filter that requires all fields
    f3 = lambda m: m.get("type") is not None and m.get("priority") is not None
    r3 = db.search(q, top_k=10, filter=f3)
    assert {x["id"] for x in r3} == {"a"}, f"Required fields filter failed: got {[x['id'] for x in r3]}"
    
    os.remove(path)

def test_filter_performance():
    """Test filter performance with larger datasets"""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        path = tf.name
    
    db = VectorLiteDB(path, dimension=8)
    
    # Insert larger dataset
    import random
    categories = ["A", "B", "C", "D", "E"]
    priorities = [1, 2, 3, 4, 5]
    
    for i in range(1000):
        vector = [random.random() for _ in range(8)]
        metadata = {
            "id": i,
            "category": random.choice(categories),
            "priority": random.choice(priorities),
            "active": random.choice([True, False]),
            "score": random.randint(0, 100)
        }
        db.insert(f"item_{i}", vector, metadata)
    
    q = [0.5] * 8
    
    # Test various filter complexities
    import time
    
    # Simple filter
    f1 = lambda m: m.get("category") == "A"
    t0 = time.time()
    r1 = db.search(q, top_k=50, filter=f1)
    t1 = time.time()
    print(f"Simple filter: {len(r1)} results in {1000*(t1-t0):.3f}ms")
    
    # Complex filter
    f2 = lambda m: (m.get("category") in ["A", "B"] and 
                   m.get("priority", 0) >= 3 and 
                   m.get("active", False) and 
                   m.get("score", 0) > 50)
    t0 = time.time()
    r2 = db.search(q, top_k=50, filter=f2)
    t1 = time.time()
    print(f"Complex filter: {len(r2)} results in {1000*(t1-t0):.3f}ms")
    
    # Verify filter results are correct
    for result in r1:
        assert result["metadata"]["category"] == "A"
    
    for result in r2:
        meta = result["metadata"]
        assert meta["category"] in ["A", "B"]
        assert meta["priority"] >= 3
        assert meta["active"] is True
        assert meta["score"] > 50
    
    os.remove(path)

def test_filter_edge_cases():
    """Test edge cases in filtering"""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        path = tf.name
    
    db = VectorLiteDB(path, dimension=2)
    
    # Insert data with edge case values
    test_data = [
        ("a", [1, 0], {"empty_list": [], "empty_string": "", "zero": 0, "false": False}),
        ("b", [0, 1], {"none_list": None, "none_string": None, "negative": -1, "true": True}),
        ("c", [0.5, 0.5], {"large_list": [1, 2, 3, 4, 5], "long_string": "a" * 100, "float": 3.14}),
    ]
    
    for id_val, vector, metadata in test_data:
        db.insert(id_val, vector, metadata)
    
    q = [0.9, 0.1]
    
    # Test empty list handling
    f1 = lambda m: len(m.get("empty_list", [])) == 0
    r1 = db.search(q, top_k=10, filter=f1)
    assert {x["id"] for x in r1} == {"a"}, f"Empty list filter failed: got {[x['id'] for x in r1]}"
    
    # Test None handling
    f2 = lambda m: m.get("none_list") is None
    r2 = db.search(q, top_k=10, filter=f2)
    assert {x["id"] for x in r2} == {"b"}, f"None filter failed: got {[x['id'] for x in r2]}"
    
    # Test zero/false handling
    f3 = lambda m: m.get("zero", 1) == 0 and m.get("false", True) is False
    r3 = db.search(q, top_k=10, filter=f3)
    assert {x["id"] for x in r3} == {"a"}, f"Zero/false filter failed: got {[x['id'] for x in r3]}"
    
    # Test negative numbers
    f4 = lambda m: m.get("negative", 0) < 0
    r4 = db.search(q, top_k=10, filter=f4)
    assert {x["id"] for x in r4} == {"b"}, f"Negative number filter failed: got {[x['id'] for x in r4]}"
    
    # Test large values
    f5 = lambda m: len(m.get("large_list", [])) > 3
    r5 = db.search(q, top_k=10, filter=f5)
    assert {x["id"] for x in r5} == {"c"}, f"Large list filter failed: got {[x['id'] for x in r5]}"
    
    os.remove(path)

def test_filter_with_unicode():
    """Test filtering with Unicode characters"""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        path = tf.name
    
    db = VectorLiteDB(path, dimension=3)
    
    # Insert data with Unicode metadata
    test_data = [
        ("a", [1, 0, 0], {"name": "café", "city": "北京", "emoji": "🚀"}),
        ("b", [0, 1, 0], {"name": "naïve", "city": "東京", "emoji": "🎉"}),
        ("c", [0, 0, 1], {"name": "résumé", "city": "São Paulo", "emoji": "🌟"}),
    ]
    
    for id_val, vector, metadata in test_data:
        db.insert(id_val, vector, metadata)
    
    q = [0.9, 0.1, 0]
    
    # Test Unicode string matching
    f1 = lambda m: "é" in m.get("name", "")
    r1 = db.search(q, top_k=10, filter=f1)
    assert {x["id"] for x in r1} == {"a", "c"}, f"Unicode string filter failed: got {[x['id'] for x in r1]}"
    
    # Test Unicode city matching
    f2 = lambda m: m.get("city") in ["北京", "東京"]
    r2 = db.search(q, top_k=10, filter=f2)
    assert {x["id"] for x in r2} == {"a", "b"}, f"Unicode city filter failed: got {[x['id'] for x in r2]}"
    
    # Test emoji matching
    f3 = lambda m: "🚀" in m.get("emoji", "")
    r3 = db.search(q, top_k=10, filter=f3)
    assert {x["id"] for x in r3} == {"a"}, f"Emoji filter failed: got {[x['id'] for x in r3]}"
    
    os.remove(path)

def test_filter_stability():
    """Test that filters are stable across multiple searches"""
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        path = tf.name
    
    db = VectorLiteDB(path, dimension=4)
    
    # Insert test data
    for i in range(100):
        vector = [i/100, (i+1)/100, (i+2)/100, (i+3)/100]
        metadata = {"id": i, "even": i % 2 == 0, "mod3": i % 3}
        db.insert(f"item_{i}", vector, metadata)
    
    q = [0.5, 0.5, 0.5, 0.5]
    f = lambda m: m.get("even", False) and m.get("mod3", 0) == 0
    
    # Run the same filter multiple times
    results = []
    for _ in range(10):
        r = db.search(q, top_k=20, filter=f)
        results.append([x["id"] for x in r])
    
    # All results should be identical
    first_result = results[0]
    for i, result in enumerate(results[1:], 1):
        assert result == first_result, f"Filter result {i} differs from first: {result} vs {first_result}"
    
    # Verify the filter logic is correct
    for result in results[0]:
        item_id = int(result.split("_")[1])
        assert item_id % 2 == 0, f"Item {item_id} should be even"
        assert item_id % 3 == 0, f"Item {item_id} should be divisible by 3"
    
    os.remove(path)

if __name__ == "__main__":
    test_complex_filters()
    test_filter_with_none_values()
    test_filter_performance()
    test_filter_edge_cases()
    test_filter_with_unicode()
    test_filter_stability()
    print("All metadata filter tests passed!")
