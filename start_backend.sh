#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Use the .venv's site-packages alongside the project root
VENV_SITE="$DIR/.venv/lib/python3.14/site-packages"
export PYTHONPATH="$VENV_SITE:$DIR"

# Prefer Homebrew Python 3.14 (matches .venv), then fall back
if [ -x "/opt/homebrew/bin/python3.14" ]; then
    PYTHON_CMD="/opt/homebrew/bin/python3.14"
elif [ -x "/opt/homebrew/bin/python3" ]; then
    PYTHON_CMD="/opt/homebrew/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

echo "=================================================="
echo "♟ ChessMind AI Backend Service"
echo "Using Python: $PYTHON_CMD"
echo "Starting FastAPI on http://localhost:8000..."
echo "=================================================="

exec "$PYTHON_CMD" -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload

