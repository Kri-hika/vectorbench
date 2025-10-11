#!/usr/bin/env python3
"""
Interactive VectorLiteDB Learning Script

This script helps you understand VectorLiteDB by doing simple experiments
that show you what's happening under the hood.
"""

import os
import tempfile
import time
import numpy as np
from vectorlitedb import VectorLiteDB

def print_header(title):
    print(f"\n{'='*60}")
    print(f"🧠 {title}")
    print('='*60)

def print_step(step, description):
    print(f"\n📝 Step {step}: {description}")

def wait_for_user():
    input("\n⏸️  Press Enter to continue...")

def experiment_1_what_is_similarity():
    """Show what similarity scores actually mean"""
    print_header("EXPERIMENT 1: What Do Similarity Scores Mean?")
    
    print("""
    When you search, VectorLiteDB gives each result a "similarity score".
    But what do these numbers actually mean?
    
    Let's find out by creating some simple examples...
    """)
    
    wait_for_user()
    
    # Create a simple database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    db = VectorLiteDB(db_path, dimension=3, distance_metric="cosine")
    
    print_step(1, "Adding some simple documents")
    
    # Add documents with known relationships
    documents = [
        ("cat", [1, 0, 0], "A furry animal that meows"),
        ("dog", [0.9, 0.1, 0], "A furry animal that barks"), 
        ("car", [0, 1, 0], "A vehicle with wheels"),
        ("truck", [0, 0.9, 0.1], "A big vehicle with wheels"),
        ("computer", [0, 0, 1], "An electronic device"),
    ]
    
    for word, vector, description in documents:
        db.insert(word, vector, {"description": description})
        print(f"  Added: {word} → {description}")
    
    print_step(2, "Searching for 'cat' and seeing similarity scores")
    
    # Search for cat
    results = db.search([1, 0, 0], top_k=3)  # Same vector as cat
    
    print(f"\n🔍 Searching for 'cat' (vector: [1, 0, 0]):")
    for result in results:
        print(f"  {result['id']}: similarity = {result['similarity']:.3f}")
        print(f"    Description: {result['metadata']['description']}")
    
    print_step(3, "Understanding what the numbers mean")
    
    print(f"""
    💡 What you just saw:
    
    • 'cat' has similarity = 1.000 (perfect match - same vector!)
    • 'dog' has similarity = 0.995 (very similar - vectors are almost the same)
    • 'car' has similarity = 0.000 (completely different - vectors point in different directions)
    
    🎯 Key insight: Similarity scores tell you how "alike" two things are.
    Higher numbers = more similar, lower numbers = more different.
    """)
    
    # Clean up
    os.unlink(db_path)

def experiment_2_why_parity_matters():
    """Show why we need to verify VectorLiteDB gives correct results"""
    print_header("EXPERIMENT 2: Why Do We Need Parity Checks?")
    
    print("""
    A "parity check" compares VectorLiteDB results to a "gold standard" algorithm.
    But why do we need this? Let's see what could go wrong...
    """)
    
    wait_for_user()
    
    print_step(1, "Creating a test with known correct answers")
    
    # Create test data where we know the right answers
    np.random.seed(42)  # Make it reproducible
    N = 100
    D = 4
    
    # Create vectors
    X = np.random.randn(N, D).astype(np.float32)
    query = np.random.randn(D).astype(np.float32)
    
    print(f"Created {N} random vectors in {D} dimensions")
    print(f"Query vector: {query}")
    
    print_step(2, "Computing the 'gold standard' answer with NumPy")
    
    # NumPy brute force (the "correct" answer)
    def numpy_search(X, q, k=3):
        # Normalize vectors for cosine similarity
        X_norm = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        q_norm = q / (np.linalg.norm(q) + 1e-9)
        
        # Compute similarities
        similarities = X_norm @ q_norm
        
        # Get top-k indices
        top_indices = np.argsort(-similarities)[:k]
        return top_indices.tolist(), similarities[top_indices]
    
    numpy_indices, numpy_scores = numpy_search(X, query, k=3)
    
    print(f"NumPy (gold standard) top-3 results:")
    for i, (idx, score) in enumerate(zip(numpy_indices, numpy_scores)):
        print(f"  {i+1}. Vector {idx}: similarity = {score:.4f}")
    
    print_step(3, "Testing VectorLiteDB with the same data")
    
    # VectorLiteDB
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    db = VectorLiteDB(db_path, dimension=D, distance_metric="cosine")
    
    # Insert vectors
    for i, vector in enumerate(X):
        db.insert(f"v{i}", vector.tolist(), {"index": i})
    
    # Search
    results = db.search(query.tolist(), top_k=3)
    vldb_indices = [int(r['id'][1:]) for r in results]  # Extract index from "v123"
    vldb_scores = [r['similarity'] for r in results]
    
    print(f"VectorLiteDB top-3 results:")
    for i, (idx, score) in enumerate(zip(vldb_indices, vldb_scores)):
        print(f"  {i+1}. Vector {idx}: similarity = {score:.4f}")
    
    print_step(4, "Comparing the results")
    
    numpy_set = set(numpy_indices)
    vldb_set = set(vldb_indices)
    
    if numpy_set == vldb_set:
        print("✅ SUCCESS: VectorLiteDB found the same results as NumPy!")
        print("   This means VectorLiteDB is working correctly.")
    else:
        print("❌ PROBLEM: VectorLiteDB found different results!")
        print(f"   NumPy found: {sorted(numpy_set)}")
        print(f"   VectorLiteDB found: {sorted(vldb_set)}")
        print("   This would mean your search results are wrong!")
    
    print(f"""
    💡 Why this matters:
    
    If VectorLiteDB gave different results than the "gold standard",
    it would mean your search is returning wrong answers to users.
    
    The parity check ensures VectorLiteDB is mathematically correct.
    """)
    
    # Clean up
    os.unlink(db_path)

def experiment_3_why_speed_matters():
    """Show why search speed is important"""
    print_header("EXPERIMENT 3: Why Does Search Speed Matter?")
    
    print("""
    VectorLiteDB uses "brute force" search - it checks every document.
    Let's see how this affects speed as you add more documents...
    """)
    
    wait_for_user()
    
    print_step(1, "Testing search speed with different amounts of data")
    
    sizes = [100, 500, 1000, 2000]
    results = []
    
    for N in sizes:
        print(f"  Testing with {N} documents...")
        
        # Create test data
        X = np.random.randn(N, 4).astype(np.float32)
        query = np.random.randn(4).astype(np.float32)
        
        # Create database
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            db_path = tmp.name
        
        db = VectorLiteDB(db_path, dimension=4, distance_metric="cosine")
        
        # Insert data
        for i, vector in enumerate(X):
            db.insert(f"v{i}", vector.tolist(), {})
        
        # Time the search
        start_time = time.time()
        db.search(query.tolist(), top_k=5)
        search_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        results.append((N, search_time))
        print(f"    Search time: {search_time:.1f}ms")
        
        # Clean up
        os.unlink(db_path)
    
    print_step(2, "Analyzing the results")
    
    print(f"\n📊 Search Speed Results:")
    print(f"{'Documents':<12} {'Search Time':<12} {'Speed Rating'}")
    print("-" * 40)
    
    for N, time_ms in results:
        if time_ms < 10:
            rating = "⚡ Lightning"
        elif time_ms < 50:
            rating = "✅ Fast"
        elif time_ms < 100:
            rating = "⚠️  Noticeable"
        else:
            rating = "❌ Slow"
        
        print(f"{N:<12} {time_ms:<12.1f}ms {rating}")
    
    print_step(3, "Understanding the pattern")
    
    print(f"""
    💡 What you just saw:
    
    • More documents = slower search (this is expected!)
    • VectorLiteDB checks every document (brute force)
    • The relationship is roughly linear: 2x documents ≈ 2x time
    
    🎯 Real-world impact:
    • < 50ms: Users don't notice any delay
    • 50-100ms: Users notice but it's acceptable  
    • > 100ms: Users start to feel the system is slow
    • > 500ms: Users get frustrated and may leave
    
    📈 Planning for growth:
    If you have 1,000 documents and search takes 20ms,
    then 10,000 documents will take ~200ms (getting slow!).
    """)
    
    wait_for_user()

def experiment_4_what_happens_when_things_break():
    """Show why crash testing matters"""
    print_header("EXPERIMENT 4: What Happens When Things Go Wrong?")
    
    print("""
    What if your app crashes while adding documents?
    Will you lose all your data? Let's find out...
    """)
    
    wait_for_user()
    
    print_step(1, "Creating a database and adding some data")
    
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        db_path = tmp.name
    
    db = VectorLiteDB(db_path, dimension=3, distance_metric="cosine")
    
    # Add some documents
    for i in range(5):
        db.insert(f"doc_{i}", [i, i+1, i+2], {"content": f"Document {i}"})
    
    print(f"Added 5 documents. Database now has {len(db)} documents.")
    
    print_step(2, "Simulating a crash by closing the database abruptly")
    
    # This simulates what happens when the app crashes
    del db  # Close the database connection
    
    print("Database connection closed (simulating crash)...")
    
    print_step(3, "Reopening the database to see if data survived")
    
    # Reopen the database
    db = VectorLiteDB(db_path, dimension=3)
    
    recovered_count = len(db)
    print(f"Recovered database has {recovered_count} documents.")
    
    if recovered_count == 5:
        print("✅ SUCCESS: All data survived the crash!")
        print("   This means VectorLiteDB is safe to use.")
    else:
        print(f"❌ PROBLEM: Expected 5 documents, but found {recovered_count}")
        print("   This would mean data loss in a crash!")
    
    print_step(4, "Verifying the data is actually correct")
    
    # Check if we can still search
    results = db.search([1, 2, 3], top_k=3)
    print(f"Search still works! Found {len(results)} results.")
    
    for result in results:
        print(f"  {result['id']}: {result['metadata']['content']}")
    
    print(f"""
    💡 Why this matters:
    
    In real applications, things go wrong:
    • App crashes
    • Computer shuts down unexpectedly  
    • Network issues
    • Power outages
    
    If your vector database can't survive these events,
    you could lose all your search data!
    
    ✅ VectorLiteDB is designed to be crash-safe.
    """)
    
    # Clean up
    os.unlink(db_path)

def main():
    print("🎓 VectorLiteDB Learning Lab")
    print("=" * 60)
    print("""
    This interactive lab will help you understand VectorLiteDB
    by doing simple experiments that show what's happening
    under the hood.
    
    Each experiment answers a real question you'd have when
    building a search system.
    """)
    
    experiments = [
        ("What Do Similarity Scores Mean?", experiment_1_what_is_similarity),
        ("Why Do We Need Parity Checks?", experiment_2_why_parity_matters),
        ("Why Does Search Speed Matter?", experiment_3_why_speed_matters),
        ("What Happens When Things Break?", experiment_4_what_happens_when_things_break),
    ]
    
    print(f"\nAvailable experiments:")
    for i, (title, _) in enumerate(experiments, 1):
        print(f"  {i}. {title}")
    
    print(f"\nOptions:")
    print(f"  • Type a number (1-{len(experiments)}) to run that experiment")
    print(f"  • Type 'all' to run all experiments")
    print(f"  • Type 'quit' to exit")
    
    while True:
        choice = input(f"\n🎯 What would you like to do? ").strip().lower()
        
        if choice == 'quit':
            print("👋 Thanks for learning about VectorLiteDB!")
            break
        elif choice == 'all':
            for title, func in experiments:
                func()
                wait_for_user()
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(experiments):
                title, func = experiments[idx]
                func()
            else:
                print(f"❌ Please enter a number between 1 and {len(experiments)}")
        else:
            print("❌ Please enter a number, 'all', or 'quit'")

if __name__ == "__main__":
    main()
