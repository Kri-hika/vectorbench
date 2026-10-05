# VectorBench API: semantic search over uploaded documents
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/hf-cache \
    VB_DB_PATH=/app/data/kb.db \
    VB_DOCS_DIR=/app/docs

# System deps for sentence-transformers/torch (manylinux wheels should suffice, but add basics)
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage layer cache
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Bake the embedding model into the image so containers start without a network download.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
# Use only the baked copy at runtime, so a pod without internet access does not stall on the Hub.
ENV HF_HUB_OFFLINE=1

# Application code only; documents and the index live on mounted volumes (see .dockerignore).
COPY *.py /app/

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"

# Incremental sync (skips unchanged files), then serve. Restarts no longer re-embed the corpus.
CMD ["/bin/sh", "-c", "python ingest.py && exec uvicorn app:app --host 0.0.0.0 --port 8000"]
