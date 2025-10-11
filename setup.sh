#!/bin/bash

echo "🚀 VectorBench Setup"
echo "===================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Check if docs directory exists and has files
if [ ! -d "docs" ] || [ -z "$(ls -A docs 2>/dev/null)" ]; then
    echo "📄 Creating sample documents..."
    mkdir -p docs
    echo "VectorLiteDB is a minimal, single-file vector database intended for local development and offline RAG." > docs/sample_1.txt
    echo "Replace files in docs/ with your own notes. Re-run python ingest.py to rebuild the index." > docs/sample_2.txt
fi

# Ingest documents
echo "🔄 Ingesting documents..."
python ingest.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "🚀 To start VectorBench:"
echo "   source .venv/bin/activate"
echo "   uvicorn app:app --reload"
echo ""
echo "🌐 Then open: frontend/index.html"
echo ""
echo "🧪 To run tests:"
echo "   python run_comprehensive_tests.py --quick"
