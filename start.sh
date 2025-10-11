#!/usr/bin/env bash
set -euo pipefail

echo "🚀 Starting VectorBench"
echo "======================="

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
fi

# Check if dependencies are installed
echo "🔍 Checking dependencies..."
python -c "import sentence_transformers, vectorlitedb, fastapi" 2>/dev/null || {
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
}

# Ingest documents
echo "📄 Ingesting documents..."
python ingest.py

echo ""
echo "✅ Setup complete! Starting services..."
echo ""

# Start API server in background
echo "🌐 Starting API server..."
uvicorn app:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

# Wait a moment for server to start
sleep 3

# Open frontend
echo "🎨 Opening frontend..."
if command -v open &> /dev/null; then
    open frontend/index.html
elif command -v xdg-open &> /dev/null; then
    xdg-open frontend/index.html
else
    echo "Please manually open: frontend/index.html"
fi

echo ""
echo "🎉 VectorBench is running!"
echo "=========================="
echo "🌐 Frontend: frontend/index.html (opened in browser)"
echo "🔗 API: http://127.0.0.1:8000"
echo "📚 API Docs: http://127.0.0.1:8000/docs"
echo ""
echo "💡 Try these in the web interface:"
echo "   • Search for documents"
echo "   • Click 'Refresh Metrics' to see performance"
echo "   • Click 'Run Parity Check' to verify accuracy"
echo "   • Click 'Run Quick Bench' to test performance"
echo ""
echo "Press Ctrl+C to stop the server"

# Wait for user to stop
wait $API_PID

