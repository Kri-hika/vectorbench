from fastapi import FastAPI, Query, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from sentence_transformers import SentenceTransformer
from vectorlitedb import VectorLiteDB
from collections import deque
import time, statistics
import os
import glob
import tempfile
import io

# Document parsing imports
import PyPDF2
from docx import Document
from pptx import Presentation
import openpyxl

DB_PATH = "kb.db"
DIM = 384

app = FastAPI(title="VectorBench API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # local demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = SentenceTransformer("all-MiniLM-L6-v2")
db = VectorLiteDB(DB_PATH, dimension=DIM)  # reopen existing DB

# --- simple in-memory metrics store ---
LATENCIES_MS = deque(maxlen=500)  # last 500 searches
LAST_Q = None

class SearchResponseItem(BaseModel):
    id: str
    similarity: float
    metadata: Dict[str, Any]

# Document parsing functions
def extract_text_from_pdf(content: bytes) -> str:
    """Extract text from PDF content"""
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"
        return text.strip()
    except Exception as e:
        raise Exception(f"Failed to parse PDF: {str(e)}")

def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX content"""
    try:
        doc = Document(io.BytesIO(content))
        text = ""
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
        return text.strip()
    except Exception as e:
        raise Exception(f"Failed to parse DOCX: {str(e)}")

def extract_text_from_pptx(content: bytes) -> str:
    """Extract text from PPTX content"""
    try:
        prs = Presentation(io.BytesIO(content))
        text = ""
        for slide in prs.slides:
            for shape in slide.shapes:
                if hasattr(shape, "text"):
                    text += shape.text + "\n"
        return text.strip()
    except Exception as e:
        raise Exception(f"Failed to parse PPTX: {str(e)}")

def extract_text_from_xlsx(content: bytes) -> str:
    """Extract text from XLSX content"""
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(content))
        text = ""
        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
            for row in sheet.iter_rows(values_only=True):
                row_text = " ".join(str(cell) for cell in row if cell is not None)
                if row_text.strip():
                    text += row_text + "\n"
        return text.strip()
    except Exception as e:
        raise Exception(f"Failed to parse XLSX: {str(e)}")

def extract_text_from_file(content: bytes, filename: str) -> str:
    """Extract text from various file formats"""
    file_ext = filename.lower().split('.')[-1]
    
    if file_ext == 'txt':
        return content.decode('utf-8', errors='ignore')
    elif file_ext == 'md':
        return content.decode('utf-8', errors='ignore')
    elif file_ext == 'pdf':
        return extract_text_from_pdf(content)
    elif file_ext == 'docx':
        return extract_text_from_docx(content)
    elif file_ext == 'pptx':
        return extract_text_from_pptx(content)
    elif file_ext == 'xlsx':
        return extract_text_from_xlsx(content)
    else:
        raise Exception(f"Unsupported file type: .{file_ext}")

def batch_insert_optimized(db, vectors_data, batch_size=100):
    """
    Optimized batch insert that minimizes transaction overhead
    vectors_data: list of tuples (id, vector, metadata)
    """
    import time
    total = len(vectors_data)
    times = []
    
    for i in range(0, total, batch_size):
        batch = vectors_data[i:i+batch_size]
        t0 = time.time()
        for id, vec, meta in batch:
            db.insert(id, vec, meta)
        times.append(time.time() - t0)
        
        # Progress feedback
        if (i + len(batch)) % 500 == 0:
            avg_time = sum(times) / len(times)
            remaining = (total - i) / batch_size * avg_time
            print(f"  Progress: {i+len(batch)}/{total} ({remaining:.1f}s remaining)")
    
    return sum(times)


@app.get("/health")
def health():
    return {"ok": True, "vectors": len(db)}

@app.get("/metrics")
def metrics():
    vals = list(LATENCIES_MS)
    if vals:
        p50 = statistics.median(vals)
        # approx p95 via quantiles; if too few, just use max
        try:
            p95 = statistics.quantiles(vals, n=20)[18]
        except Exception:
            p95 = max(vals)
    else:
        p50 = p95 = None
    return {
        "vectors": len(db),
        "recent": vals[-10:],
        "p50_ms": round(p50,3) if p50 is not None else None,
        "p95_ms": round(p95,3) if p95 is not None else None,
        "last_query": LAST_Q,
    }

@app.get("/search", response_model=List[SearchResponseItem])
def search(q: str = Query(..., description="Query text"),
           k: int = Query(5, ge=1, le=50),
           file: Optional[str] = Query(None, description="Optional filename filter")):
    global LAST_Q
    q_vec = model.encode(q).tolist()

    meta_filter = None
    if file:
        meta_filter = lambda m: m.get("file") == file

    t0 = time.time()
    results = db.search(query=q_vec, top_k=k, filter=meta_filter)
    dt_ms = 1000 * (time.time() - t0)
    LATENCIES_MS.append(round(dt_ms,3))
    LAST_Q = {"q": q, "k": k, "file": file, "latency_ms": round(dt_ms,3)}
    return results

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and ingest a new document"""
    supported_extensions = ('.txt', '.md', '.pdf', '.docx', '.pptx', '.xlsx')
    if not file.filename.lower().endswith(supported_extensions):
        return JSONResponse(
            status_code=400,
            content={"error": f"Only {', '.join(supported_extensions)} files are supported"}
        )
    
    try:
        # Read file content
        content = await file.read()
        
        # Extract text based on file type
        text = extract_text_from_file(content, file.filename)
        
        if not text.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "No text content found in file"}
            )
        
        # Save original file to docs directory
        docs_dir = "docs"
        os.makedirs(docs_dir, exist_ok=True)
        file_path = os.path.join(docs_dir, file.filename)
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Also save extracted text for reference
        text_file_path = os.path.join(docs_dir, f"{file.filename}.txt")
        with open(text_file_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        # Ingest the new document
        CHUNK_CHARS = 800
        
        def chunk_text(t: str, n: int) -> List[str]:
            return [t[i:i + n] for i in range(0, len(t), n)] if t else []
        
        chunks = chunk_text(text, CHUNK_CHARS)
        if not chunks:
            return JSONResponse(
                status_code=400,
                content={"error": "File appears to be empty after text extraction"}
            )
        
        # Add chunks to database
        for idx, chunk in enumerate(chunks):
            vec = model.encode(chunk).tolist()
            uid = f"{file.filename}::{idx}"
            meta = {
                "file": file.filename, 
                "index": idx, 
                "chunk": chunk,
                "file_type": file.filename.lower().split('.')[-1]
            }
            db.insert(id=uid, vector=vec, metadata=meta)
        
        return {
            "message": f"Successfully uploaded and ingested {file.filename}",
            "chunks": len(chunks),
            "total_vectors": len(db),
            "file_type": file.filename.lower().split('.')[-1],
            "extracted_text_length": len(text)
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to process file: {str(e)}"}
        )

@app.get("/files")
def list_files():
    """List all available files in the knowledge base with actual chunk counts"""
    patterns = ["docs/*.txt", "docs/*.md", "docs/*.pdf", "docs/*.docx", "docs/*.pptx", "docs/*.xlsx"]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern))
    
    # Filter out .txt files that are just extracted text versions
    original_files = []
    for f in files:
        filename = os.path.basename(f)
        # Skip .txt files that are extracted versions of other files
        if not (filename.endswith('.txt') and any(filename.replace('.txt', ext) in [os.path.basename(g) for g in files] for ext in ['.pdf', '.docx', '.pptx', '.xlsx'])):
            original_files.append(filename)
    
    # Get actual chunk counts by doing a broad search and filtering results
    file_stats = []
    file_counts = {}
    
    # Do one broad search to get all vectors
    try:
        dummy_vec = model.encode("the").tolist()  # Common word to get all docs
        all_results = db.search(query=dummy_vec, top_k=10000)
        
        # Count chunks per file
        if all_results and isinstance(all_results, list):
            for result in all_results:
                if isinstance(result, dict) and 'metadata' in result:
                    file = result['metadata'].get('file', '')
                    if file:
                        file_counts[file] = file_counts.get(file, 0) + 1
    except Exception as e:
        print(f"Warning: Failed to count chunks - {str(e)}")
        file_counts = {}
    
    # Build response with counts
    for filename in sorted(original_files):
        count = file_counts.get(filename, 0)
        file_stats.append({
            "filename": filename,
            "count": count,
            "in_database": count > 0
        })
    
    return file_stats

# --- lightweight, on-demand micro-benchmarks ---
@app.get("/bench")
def bench(N: int = 500, k: int = 5):
    import numpy as np, os
    # Updating temp benchmark db location (due to icloud db sync issue)
    tmp = os.path.expanduser("~/Local/vectorbench-db/_bench_tmp.db")
    # tmp = "_bench_tmp.db"

    if os.path.exists(tmp):
        os.remove(tmp)
    
    # Create database
    db2 = VectorLiteDB(tmp, dimension=DIM, distance_metric="cosine")
    X = np.random.randn(N, DIM).astype("float32")

    # Prepare data for batch insert
    vectors_data = [(f"b{i}", X[i].tolist(), {"i": i}) for i in range(N)]
    
    # Measure insert performance with batching
    t0 = time.time()
    total_time = batch_insert_optimized(db2, vectors_data, batch_size=50)
    ins_ms = 1000 * total_time / N
    
    # Measure search
    q = np.random.randn(DIM).astype("float32").tolist()
    t1 = time.time()
    _ = db2.search(q, top_k=k)
    search_ms = 1000*(time.time()-t1)
    
    size_mb = os.path.getsize(tmp)/1e6
    
    # Cleanup
    try:
        os.remove(tmp)
    except Exception:
        pass
    return {"N": N, "avg_insert_ms": round(ins_ms,3), "search_ms": round(search_ms,3), "file_MB": round(size_mb,2), "note": "Optimized batching used"}

@app.get("/parity")
def parity(K: int = 5):
    import numpy as np, os
    def topk_numpy(X, q, k):
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        qn = q / (np.linalg.norm(q) + 1e-9)
        sims = Xn @ qn
        idx = np.argsort(-sims)[:k]
        return idx.tolist()
    N=1000; D=DIM
    rng = np.random.default_rng(0)
    X = rng.standard_normal((N, D)).astype("float32")
    q = rng.standard_normal(D).astype("float32")
    np_ids = topk_numpy(X, q, K)
    tmp = "_parity.db"
    if os.path.exists(tmp): os.remove(tmp)
    dbp = VectorLiteDB(tmp, dimension=D)
    
    # Use batch insert optimization for much faster performance
    vectors_data = [(f"v{i}", X[i].tolist(), {"i": i}) for i in range(N)]
    batch_insert_optimized(dbp, vectors_data, batch_size=100)
    
    res = dbp.search(q.tolist(), top_k=K)
    vl_ids = [int(r['id'][1:]) for r in res]
    try:
        os.remove(tmp)
    except Exception:
        pass
    ok = set(np_ids) == set(vl_ids)
    return {"ok": ok, "numpy_topk": np_ids, "vldb_topk": vl_ids}
