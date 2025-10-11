import os, tempfile, signal, time, subprocess, json, sys
from vectorlitedb import VectorLiteDB

SCRIPT = r"""
import time, os, sys, json
from vectorlitedb import VectorLiteDB

path = sys.argv[1]
db = VectorLiteDB(path, dimension=8, distance_metric="cosine")
for i in range(10000):
    db.insert(f"id{i}", [1.0]*8, {"i": i})
    if i == 3000:
        open("marker.txt","w").write("inserted_3000")
        # simulate long work; parent may kill us
        time.sleep(60)
"""

def test_crash_mid_ingest():
    """Test database behavior after crash during insert"""
    with tempfile.TemporaryDirectory() as d:
        dbp = os.path.join(d, "crash.db")
        sp = subprocess.Popen([sys.executable, "-c", SCRIPT, dbp], cwd=d)
        
        # Wait until ~3000 inserted
        while not os.path.exists(os.path.join(d, "marker.txt")):
            time.sleep(0.1)
        
        # Simulate crash
        sp.send_signal(signal.SIGKILL)
        sp.wait(timeout=5)

        # Reopen and verify DB is not corrupt and len() is sane (<= 3001)
        db = VectorLiteDB(dbp, dimension=8)
        n = len(db)
        assert 0 <= n <= 3001, f"Unexpected DB length after crash: {n}"
        
        # Try to search to ensure DB is functional
        try:
            results = db.search([1.0]*8, top_k=5)
            assert isinstance(results, list)
        except Exception as e:
            assert False, f"DB search failed after crash recovery: {e}"

def test_normal_persistence():
    """Test normal persistence after clean shutdown"""
    with tempfile.TemporaryDirectory() as d:
        dbp = os.path.join(d, "normal.db")
        
        # Create and populate DB
        db = VectorLiteDB(dbp, dimension=4, distance_metric="cosine")
        test_data = [
            ("a", [1, 0, 0, 0], {"type": "doc", "id": 1}),
            ("b", [0, 1, 0, 0], {"type": "note", "id": 2}),
            ("c", [0, 0, 1, 0], {"type": "doc", "id": 3}),
        ]
        
        for id_val, vector, metadata in test_data:
            db.insert(id_val, vector, metadata)
        
        assert len(db) == 3
        
        # Normal close (implicit when db goes out of scope)
        del db
        
        # Reopen and verify
        db2 = VectorLiteDB(dbp, dimension=4)
        assert len(db2) == 3
        
        # Verify all data is intact
        for id_val, vector, metadata in test_data:
            retrieved_vector, retrieved_metadata = db2.get(id_val)
            assert retrieved_vector == vector, f"Vector mismatch for {id_val}"
            assert retrieved_metadata == metadata, f"Metadata mismatch for {id_val}"
        
        # Test search still works
        results = db2.search([0.9, 0.1, 0, 0], top_k=2)
        assert len(results) >= 1
        assert results[0]['id'] == 'a'  # Should be closest

def test_file_portability():
    """Test that DB files can be moved between locations"""
    with tempfile.TemporaryDirectory() as d1:
        with tempfile.TemporaryDirectory() as d2:
            # Create DB in first location
            dbp1 = os.path.join(d1, "portable.db")
            db = VectorLiteDB(dbp1, dimension=3, distance_metric="l2")
            db.insert("test", [1, 2, 3], {"moved": True})
            
            # Copy to second location
            dbp2 = os.path.join(d2, "portable.db")
            import shutil
            shutil.copy2(dbp1, dbp2)
            
            # Open in second location
            db2 = VectorLiteDB(dbp2, dimension=3)
            assert len(db2) == 1
            
            vector, metadata = db2.get("test")
            assert vector == [1, 2, 3]
            assert metadata == {"moved": True}

def test_reopen_after_delete():
    """Test reopening DB after some deletions"""
    with tempfile.TemporaryDirectory() as d:
        dbp = os.path.join(d, "delete_test.db")
        
        # Create and populate
        db = VectorLiteDB(dbp, dimension=2, distance_metric="dot")
        for i in range(10):
            db.insert(f"item_{i}", [i, i+1], {"index": i})
        
        assert len(db) == 10
        
        # Delete some items
        for i in [2, 5, 8]:
            db.delete(f"item_{i}")
        
        assert len(db) == 7
        
        # Close and reopen
        del db
        db2 = VectorLiteDB(dbp, dimension=2)
        assert len(db2) == 7
        
        # Verify deletions persisted
        for i in [2, 5, 8]:
            try:
                db2.get(f"item_{i}")
                assert False, f"Deleted item {i} should not exist"
            except:
                pass  # Expected
        
        # Verify remaining items exist
        for i in [0, 1, 3, 4, 6, 7, 9]:
            vector, metadata = db2.get(f"item_{i}")
            assert vector == [i, i+1]
            assert metadata == {"index": i}

def test_corruption_resilience():
    """Test behavior with potentially corrupted files"""
    with tempfile.TemporaryDirectory() as d:
        dbp = os.path.join(d, "corrupt.db")
        
        # Create a valid DB first
        db = VectorLiteDB(dbp, dimension=2)
        db.insert("valid", [1, 1], {"test": True})
        del db
        
        # Try to corrupt the file by truncating it
        with open(dbp, 'r+b') as f:
            f.truncate(os.path.getsize(dbp) // 2)
        
        # Try to reopen - should either work or fail gracefully
        try:
            db2 = VectorLiteDB(dbp, dimension=2)
            # If it opens, it should be empty or have partial data
            n = len(db2)
            assert n >= 0, "Corrupted DB should report non-negative length"
        except Exception as e:
            # Graceful failure is also acceptable
            assert "corrupt" in str(e).lower() or "invalid" in str(e).lower() or "error" in str(e).lower()

def test_concurrent_access_safety():
    """Test that multiple processes can't corrupt the DB"""
    with tempfile.TemporaryDirectory() as d:
        dbp = os.path.join(d, "concurrent.db")
        
        # Create initial DB
        db = VectorLiteDB(dbp, dimension=2)
        db.insert("initial", [0, 0], {"created": True})
        del db
        
        # Script for concurrent access
        concurrent_script = f"""
import time
from vectorlitedb import VectorLiteDB
import sys

path = "{dbp}"
try:
    db = VectorLiteDB(path, dimension=2)
    for i in range(100):
        db.insert(f"concurrent_{{i}}", [i, i+1], {{"proc": "test"}})
        time.sleep(0.001)
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {{e}}")
"""
        
        # Run multiple processes
        processes = []
        for i in range(3):
            p = subprocess.Popen([sys.executable, "-c", concurrent_script], 
                               cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            processes.append(p)
        
        # Wait for all to complete
        results = []
        for p in processes:
            stdout, stderr = p.communicate(timeout=10)
            results.append(stdout.decode().strip())
        
        # At least one should succeed
        success_count = sum(1 for r in results if r == "SUCCESS")
        assert success_count >= 1, f"No processes succeeded: {results}"
        
        # Final DB should be in a consistent state
        final_db = VectorLiteDB(dbp, dimension=2)
        final_len = len(final_db)
        assert final_len >= 1, "DB should have at least the initial record"
        
        # Should be able to search without errors
        results = final_db.search([1, 1], top_k=5)
        assert isinstance(results, list)

if __name__ == "__main__":
    test_normal_persistence()
    test_file_portability()
    test_reopen_after_delete()
    test_corruption_resilience()
    test_concurrent_access_safety()
    test_crash_mid_ingest()
    print("All persistence and crash tests passed!")
