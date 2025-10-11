#!/usr/bin/env bash
set -euo pipefail

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

# Check if dependencies are installed
echo "Checking dependencies..."
python -c "import sentence_transformers, vectorlitedb, fastapi" 2>/dev/null || {
    echo "Installing dependencies..."
    pip install -r requirements.txt
}

# Ingest documents and start API
echo "Ingesting documents..."
python ingest.py

echo "Starting API server..."
echo "Frontend available at: http://127.0.0.1:8000 (when served via file://)"
echo "API docs available at: http://127.0.0.1:8000/docs"

# Open frontend in browser (macOS)
if command -v open &> /dev/null; then
    echo "Opening frontend in browser..."
    open frontend/index.html
elif command -v xdg-open &> /dev/null; then
    echo "Opening frontend in browser..."
    xdg-open frontend/index.html
else
    echo "Please manually open: frontend/index.html"
fi

uvicorn app:app --host 0.0.0.0 --port 8000 --reload
