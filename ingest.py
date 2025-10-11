import os
import glob
import io
from typing import List
from sentence_transformers import SentenceTransformer
from vectorlitedb import VectorLiteDB

# Document parsing imports
import PyPDF2
from docx import Document
from pptx import Presentation
import openpyxl

DB_PATH = "kb.db"
EMBED_MODEL = "all-MiniLM-L6-v2"  # 384-dim
CHUNK_CHARS = 800                  # ~200 words

def chunk_text(t: str, n: int) -> List[str]:
    return [t[i:i + n] for i in range(0, len(t), n)] if t else []

# Document parsing functions (same as in app.py)
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

def extract_text_from_file(file_path: str) -> str:
    """Extract text from various file formats"""
    file_ext = file_path.lower().split('.')[-1]
    
    with open(file_path, 'rb') as f:
        content = f.read()
    
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

def main() -> None:
    # For demo: rebuild each time
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    print("Loading embedding model...", EMBED_MODEL)
    model = SentenceTransformer(EMBED_MODEL)

    print("Opening VectorLiteDB...", DB_PATH)
    db = VectorLiteDB(DB_PATH, dimension=384, distance_metric="cosine")

    # Find all supported files
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
            original_files.append(f)
    
    if not original_files:
        print("No docs found in docs/ — add supported files (.txt, .md, .pdf, .docx, .pptx, .xlsx) and re-run.")
        return

    total_chunks = 0
    for path in original_files:
        try:
            print(f"Processing {path}...")
            text = extract_text_from_file(path)
            
            if not text.strip():
                print(f"Warning: No text content found in {path}")
                continue
                
            chunks = chunk_text(text, CHUNK_CHARS)
            if not chunks:
                print(f"Warning: No chunks created from {path}")
                continue
                
            for idx, chunk in enumerate(chunks):
                vec = model.encode(chunk).tolist()  # 384 floats
                uid = f"{os.path.basename(path)}::{idx}"
                file_type = os.path.basename(path).lower().split('.')[-1]
                meta = {
                    "file": os.path.basename(path), 
                    "index": idx, 
                    "chunk": chunk,
                    "file_type": file_type
                }
                db.insert(id=uid, vector=vec, metadata=meta)
                total_chunks += 1
            print(f"Ingested {len(chunks)} chunks from {path}")
            
        except Exception as e:
            print(f"Error processing {path}: {str(e)}")
            continue

    print(f"Done. Total chunks: {total_chunks}; DB len: {len(db)}")
    print(f"DB file: {DB_PATH} (bytes: {os.path.getsize(DB_PATH)})")

if __name__ == "__main__":
    main()
