# VectorBench - Local Vector Database Experimentation
# Use Python slim base
FROM python:3.11-slim

# Avoid interactive tzdata etc.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# System deps for sentence-transformers/torch (manylinux wheels should suffice, but add basics)
RUN apt-get update && apt-get install -y --no-install-recommends     build-essential     git     && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first to leverage layer cache
COPY requirements.txt /app/requirements.txt

RUN pip install --upgrade pip &&     pip install --no-cache-dir -r requirements.txt

# Copy the rest
COPY . /app

# Pre-warm model to speed up first query (optional; comment out to slim image) 
# Model Caching is a good practice to speed up the first query.
# This downloads 'all-MiniLM-L6-v2' into the image layer.
RUN python - <<'PY'
from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')
print('Model cached')
PY

EXPOSE 8000

# Default command: ingest then run api
CMD ["/bin/bash", "-lc", "python ingest.py && uvicorn app:app --host 0.0.0.0 --port 8000"]
