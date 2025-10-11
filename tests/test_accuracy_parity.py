import numpy as np
from vectorlitedb import VectorLiteDB
import os, tempfile

def topk_numpy(X, q, k, metric="cosine"):
    """NumPy brute-force implementation for comparison"""
    X = X.astype(np.float32); q = q.astype(np.float32)
    if metric == "cosine":
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        qn = q / (np.linalg.norm(q) + 1e-9)
        sims = Xn @ qn
        idx = np.argsort(-sims)[:k]
        return idx, sims[idx]
    elif metric == "dot":
        sims = X @ q
        idx = np.argsort(-sims)[:k]
        return idx, sims[idx]
    elif metric == "l2":
        # VectorLiteDB seems to use a similarity transformation for L2
        # Based on testing, it appears to use: 1 / (1 + distance)
        distances = np.linalg.norm(X - q, axis=1)
        sims = 1.0 / (1.0 + distances)  # Convert distance to similarity
        idx = np.argsort(-sims)[:k]
        return idx, sims[idx]
    else:
        raise ValueError(metric)

def build_db(X, metric):
    """Build VectorLiteDB from numpy array"""
    D = X.shape[1]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    db = VectorLiteDB(tmp.name, dimension=D, distance_metric=metric)
    for i, v in enumerate(X):
        db.insert(id=f"v{i}", vector=v.tolist(), metadata={"i": i})
    return db, tmp.name

def test_parity_small_random():
    """Test accuracy parity with small random dataset"""
    rng = np.random.default_rng(0)
    N, D, K = 1000, 64, 10
    X = rng.standard_normal((N, D)).astype(np.float32)
    q = rng.standard_normal(D).astype(np.float32)
    
    for metric in ["cosine", "dot", "l2"]:
        db, path = build_db(X, metric)
        res = db.search(q.tolist(), top_k=K)
        ids_db = [int(r["id"][1:]) for r in res]  # "v123" -> 123
        ids_np, _ = topk_numpy(X, q, K, metric)
        
        # Allow minor ties / ordering differences in near-equal scores
        # Check that the top-k sets match (order may differ for ties)
        assert set(ids_db[:K]) == set(ids_np[:K]), f"Metric {metric}: DB={ids_db[:K]}, NumPy={ids_np[:K]}"
        
        # Check that similarity scores are reasonable
        for i, result in enumerate(res):
            assert isinstance(result['similarity'], (int, float)), f"Similarity should be numeric for {metric}"
            # VectorLiteDB returns similarity scores where higher is better for all metrics
            # All similarity scores should be positive and finite
            assert result['similarity'] >= 0, f"Similarity should be non-negative for {metric}: {result['similarity']}"
            assert abs(result['similarity']) < 1e6, f"Similarity too large for {metric}: {result['similarity']}"
        
        os.remove(path)

def test_parity_near_ties():
    """Test behavior with vectors that are very close (near ties)"""
    rng = np.random.default_rng(42)
    N, D, K = 100, 32, 5
    
    # Create vectors that are very similar to test tie-breaking
    base_vec = rng.standard_normal(D).astype(np.float32)
    X = np.array([base_vec + 0.001 * rng.standard_normal(D) for _ in range(N)])
    q = base_vec + 0.0005 * rng.standard_normal(D)
    
    for metric in ["cosine", "dot", "l2"]:
        db, path = build_db(X, metric)
        res = db.search(q.tolist(), top_k=K)
        ids_db = [int(r["id"][1:]) for r in res]
        ids_np, _ = topk_numpy(X, q, K, metric)
        
        # For near-ties, we just check that we get reasonable results
        # and that the top-k sets have significant overlap
        overlap = len(set(ids_db[:K]) & set(ids_np[:K]))
        assert overlap >= K // 2, f"Metric {metric}: insufficient overlap {overlap}/{K}"
        
        os.remove(path)

def test_parity_edge_cases():
    """Test edge cases: zero vectors, identical vectors, etc."""
    D = 8
    
    # Test with zero query vector
    X = np.random.randn(10, D).astype(np.float32)
    q_zero = np.zeros(D, dtype=np.float32)
    
    for metric in ["cosine", "dot", "l2"]:
        db, path = build_db(X, metric)
        
        if metric == "cosine":
            # Cosine with zero vector should handle gracefully
            res = db.search(q_zero.tolist(), top_k=3)
            assert len(res) <= 3
        else:
            # Dot and L2 should work fine with zero vector
            res = db.search(q_zero.tolist(), top_k=3)
            assert len(res) <= 3
        
        os.remove(path)
    
    # Test with identical vectors
    identical_vec = np.random.randn(D).astype(np.float32)
    X_identical = np.tile(identical_vec, (5, 1))
    
    for metric in ["cosine", "dot", "l2"]:
        db, path = build_db(X_identical, metric)
        res = db.search(identical_vec.tolist(), top_k=3)
        
        # All similarities should be very close (or identical)
        similarities = [r['similarity'] for r in res]
        if len(similarities) > 1:
            max_diff = max(similarities) - min(similarities)
            if metric == "cosine":
                assert max_diff < 1e-6, f"Identical vectors should have identical cosine similarity: {similarities}"
            elif metric == "dot":
                assert max_diff < 1e-6, f"Identical vectors should have identical dot product: {similarities}"
            elif metric == "l2":
                # L2 distance should be 0 for identical vectors
                assert all(abs(s) < 1e-6 for s in similarities), f"Identical vectors should have zero L2 distance: {similarities}"
        
        os.remove(path)

def test_parity_different_dimensions():
    """Test with different vector dimensions"""
    rng = np.random.default_rng(123)
    dimensions = [16, 32, 64, 128, 256]
    
    for D in dimensions:
        N, K = min(500, D * 10), 5  # Scale N with dimension
        X = rng.standard_normal((N, D)).astype(np.float32)
        q = rng.standard_normal(D).astype(np.float32)
        
        for metric in ["cosine", "dot", "l2"]:
            db, path = build_db(X, metric)
            res = db.search(q.tolist(), top_k=K)
            ids_db = [int(r["id"][1:]) for r in res]
            ids_np, _ = topk_numpy(X, q, K, metric)
            
            assert set(ids_db[:K]) == set(ids_np[:K]), f"D={D}, {metric}: mismatch"
            
            os.remove(path)

if __name__ == "__main__":
    test_parity_small_random()
    test_parity_near_ties()
    test_parity_edge_cases()
    test_parity_different_dimensions()
    print("All accuracy parity tests passed!")
