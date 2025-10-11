#!/bin/bash
# VectorBench Cleanup Script
# Removes temporary files, cache, and system metadata

set -e

echo "🧹 VectorBench Cleanup"
echo "====================="
echo ""

# Track what we're cleaning
CLEANED=0

# Function to report what was cleaned
report_clean() {
    local item=$1
    local count=$2
    if [ "$count" -gt 0 ]; then
        echo "  ✓ Removed $count $item"
        CLEANED=$((CLEANED + count))
    fi
}

# 1. Remove macOS .DS_Store files
echo "Removing macOS metadata files..."
DS_COUNT=$(find . -name ".DS_Store" -type f 2>/dev/null | wc -l | tr -d ' ')
find . -name ".DS_Store" -type f -delete 2>/dev/null || true
report_clean ".DS_Store files" "$DS_COUNT"

# 2. Remove Python cache directories (excluding .venv)
echo "Removing Python cache..."
PYCACHE_COUNT=$(find . -path "./.venv" -prune -o -name "__pycache__" -type d -print 2>/dev/null | wc -l | tr -d ' ')
find . -path "./.venv" -prune -o -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
report_clean "__pycache__ directories" "$PYCACHE_COUNT"

# 3. Remove .pyc files (excluding .venv)
echo "Removing compiled Python files..."
PYC_COUNT=$(find . -path "./.venv" -prune -o -name "*.pyc" -type f -print 2>/dev/null | wc -l | tr -d ' ')
find . -path "./.venv" -prune -o -name "*.pyc" -type f -delete 2>/dev/null || true
report_clean ".pyc files" "$PYC_COUNT"

# 4. Remove pytest cache
echo "Removing test cache..."
if [ -d ".pytest_cache" ]; then
    rm -rf .pytest_cache
    echo "  ✓ Removed .pytest_cache directory"
    CLEANED=$((CLEANED + 1))
fi

# 5. Remove log files
echo "Removing log files..."
LOG_COUNT=$(find . -path "./.venv" -prune -o -name "*.log" -type f -print 2>/dev/null | wc -l | tr -d ' ')
find . -path "./.venv" -prune -o -name "*.log" -type f -delete 2>/dev/null || true
report_clean "log files" "$LOG_COUNT"

# 6. Remove temporary editor files
echo "Removing editor temporary files..."
TEMP_COUNT=$(find . -name "*~" -o -name "*.swp" -o -name "*.swo" -o -name ".*.swp" 2>/dev/null | wc -l | tr -d ' ')
find . \( -name "*~" -o -name "*.swp" -o -name "*.swo" -o -name ".*.swp" \) -type f -delete 2>/dev/null || true
report_clean "temporary editor files" "$TEMP_COUNT"

# 7. Check for iCloud placeholder files (don't delete, just warn)
echo "Checking for iCloud placeholder files..."
ICLOUD_COUNT=$(find . -name "*.icloud" -type f 2>/dev/null | wc -l | tr -d ' ')
if [ "$ICLOUD_COUNT" -gt 0 ]; then
    echo "  ⚠️  Found $ICLOUD_COUNT .icloud placeholder files"
    echo "     These indicate files are stored in iCloud and not downloaded locally"
    echo "     Run: find . -name '*.icloud' to see which files"
fi

echo ""
echo "================================"
if [ "$CLEANED" -gt 0 ]; then
    echo "✅ Cleanup complete! Removed $CLEANED items."
else
    echo "✅ Nothing to clean - project is already tidy!"
fi
echo ""

# Show project size (excluding .venv)
echo "📊 Project size (excluding .venv):"
if command -v du &> /dev/null; then
    du -sh --exclude=.venv . 2>/dev/null || du -sh -I .venv . 2>/dev/null || echo "  Size check not available on this system"
fi
echo ""

