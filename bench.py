import os, time
import numpy as np
from vectorlitedb import VectorLiteDB

DB = "perf.db"
N, D = 10000, 384

if os.path.exists(DB):
    os.remove(DB)

db = VectorLiteDB(DB, dimension=D, distance_metric="cosine")
X = np.random.randn(N, D).astype("float32")
ids = [f"v{i}" for i in range(N)]

# Insert timing
start = time.time()
for i in range(N):
    db.insert(id=ids[i], vector=X[i].tolist(), metadata={"i": i})
ins_ms = 1000 * (time.time() - start) / N

# Search timing
q = np.random.randn(D).astype("float32").tolist()
start = time.time()
_ = db.search(query=q, top_k=5)
search_ms = 1000 * (time.time() - start)

size_mb = os.path.getsize(DB) / 1e6
print({
    "N": N,
    "D": D,
    "avg_insert_ms": round(ins_ms, 3),
    "search_ms": round(search_ms, 3),
    "file_MB": round(size_mb, 2)
})
