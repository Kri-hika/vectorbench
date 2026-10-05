"""Document ingestion pipeline shared by the API (app.py) and the batch ingester (ingest.py).

Owns settings, filename safety, text extraction, chunking, hashing and the embedding model,
so the upload path and the batch path cannot drift apart.
"""
from __future__ import annotations

import glob
import hashlib
import io
import os
import re
from dataclasses import dataclass
from typing import Callable, List, Optional

# --- settings (overridable per environment: local, Docker Compose, Kubernetes) ---
DB_PATH = os.getenv("VB_DB_PATH", "kb.db")
DOCS_DIR = os.getenv("VB_DOCS_DIR", "docs")
EMBED_MODEL = os.getenv("VB_EMBED_MODEL", "all-MiniLM-L6-v2")
EMBED_DIM = 384          # all-MiniLM-L6-v2 output size
CHUNK_CHARS = 800        # ~200 words; unchanged until retrieval quality is measured
MAX_UPLOAD_BYTES = 10 * 1024 * 1024   # matches client_max_body_size in nginx.conf

SUPPORTED_EXTS = (".txt", ".md", ".pdf", ".docx", ".pptx", ".xlsx")
_BINARY_EXTS = (".pdf", ".docx", ".pptx", ".xlsx")
_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._ ()-]")

Embedder = Callable[[List[str]], List[List[float]]]


class ExtractionError(ValueError):
    """The file could not be turned into text. The message is safe to show to the client."""


@dataclass
class Extraction:
    text: str
    pages_total: Optional[int] = None    # PDFs only
    pages_without_text: int = 0          # PDF pages with no text layer (usually scanned)


# --- filenames ---

def safe_filename(name: str) -> str:
    """Reduce a client-supplied filename to a plain basename that cannot escape the docs dir.

    "../app.py" -> "app.py"; "..\\..\\x.pdf" -> "x.pdf"; hidden names lose their leading dots.
    Raises ExtractionError for empty, oversized or unsupported names.
    """
    base = os.path.basename((name or "").replace("\\", "/")).strip()
    base = _UNSAFE_CHARS.sub("_", base).lstrip(".")
    if not base or len(base) > 200:
        raise ExtractionError("Invalid filename")
    if not base.lower().endswith(SUPPORTED_EXTS):
        raise ExtractionError(f"Only {', '.join(SUPPORTED_EXTS)} files are supported")
    return base


def list_source_files(docs_dir: str) -> List[str]:
    """Supported files in docs_dir, skipping 'name.pdf.txt'-style sidecars of a file that is present."""
    paths = [p for p in glob.glob(os.path.join(docs_dir, "*"))
             if os.path.isfile(p) and p.lower().endswith(SUPPORTED_EXTS)]
    names = {os.path.basename(p) for p in paths}
    sources = []
    for p in paths:
        name = os.path.basename(p)
        if name.lower().endswith(".txt") and name[:-4].lower().endswith(_BINARY_EXTS) and name[:-4] in names:
            continue  # extracted-text copy written by older versions of /upload
        sources.append(p)
    return sorted(sources)


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


# --- extraction ---

def _extract_pdf(content: bytes) -> Extraction:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise ExtractionError("PDF is encrypted")
        # extract_text() can return None or "" for image-only pages; never let that crash the join.
        pages = [(page.extract_text() or "") for page in reader.pages]
    except ExtractionError:
        raise
    except Exception as e:
        raise ExtractionError(f"Failed to parse PDF: {e}") from e
    empty = sum(1 for t in pages if not t.strip())
    return Extraction("\n".join(pages).strip(), pages_total=len(pages), pages_without_text=empty)


def _extract_docx(content: bytes) -> str:
    from docx import Document
    doc = Document(io.BytesIO(content))
    lines = [p.text for p in doc.paragraphs]
    for table in doc.tables:  # policy documents keep rates and rules in tables
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                lines.append(" | ".join(cells))
    return "\n".join(lines)


def _extract_pptx(content: bytes) -> str:
    from pptx import Presentation
    prs = Presentation(io.BytesIO(content))
    return "\n".join(shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text"))


def _extract_xlsx(content: bytes) -> str:
    import openpyxl
    # data_only=True returns computed values instead of formula strings
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    lines = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows(values_only=True):
            row_text = " ".join(str(c) for c in row if c is not None).strip()
            if row_text:
                lines.append(row_text)
    wb.close()
    return "\n".join(lines)


def extract_text(content: bytes, filename: str) -> Extraction:
    ext = os.path.splitext(filename.lower())[1]
    if ext in (".txt", ".md"):
        return Extraction(content.decode("utf-8", errors="ignore").strip())
    if ext == ".pdf":
        return _extract_pdf(content)
    parsers = {".docx": _extract_docx, ".pptx": _extract_pptx, ".xlsx": _extract_xlsx}
    if ext not in parsers:
        raise ExtractionError(f"Unsupported file type: {ext or '(none)'}")
    try:
        return Extraction(parsers[ext](content).strip())
    except Exception as e:
        raise ExtractionError(f"Failed to parse {ext[1:].upper()}: {e}") from e


def require_text(extraction: Extraction) -> str:
    """Return the text, or raise with a reason the user can act on."""
    if extraction.text:
        return extraction.text
    if extraction.pages_total:
        raise ExtractionError(
            f"No extractable text: {extraction.pages_without_text} of {extraction.pages_total} pages "
            "have no text layer (likely scanned). OCR is not supported yet.")
    raise ExtractionError("No text content found in file")


def chunk_text(text: str, n: int = CHUNK_CHARS) -> List[str]:
    return [text[i:i + n] for i in range(0, len(text), n)] if text else []


# --- embedding ---

def load_embedder(model_name: str = EMBED_MODEL) -> Embedder:
    """Load the sentence-transformer once; the returned function embeds a batch of texts."""
    from sentence_transformers import SentenceTransformer  # heavy import, deferred until needed
    model = SentenceTransformer(model_name)

    def embed(texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        return model.encode(texts, batch_size=32, show_progress_bar=False).tolist()

    return embed
