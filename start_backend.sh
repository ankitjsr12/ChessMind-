#!/usr/bin/env bash
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

# 1. Virtual Environment Detection & Setup
VENV_DIR="$DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_UVICORN="$VENV_DIR/bin/uvicorn"
VENV_PIP="$VENV_DIR/bin/pip"

if [ ! -d "$VENV_DIR" ] || [ ! -x "$VENV_PYTHON" ]; then
    echo "⚠️  Virtual environment not found at $VENV_DIR. Initializing..."
    
    # Locate best available system python3 for bootstrap
    SYSTEM_PYTHON=""
    for py in python3.11 python3.12 python3.10 python3; do
        if command -v "$py" >/dev/null 2>&1; then
            SYSTEM_PYTHON="$py"
            break
        fi
    done

    if [ -z "$SYSTEM_PYTHON" ]; then
        echo "❌ No suitable Python 3 interpreter found in PATH to create .venv."
        echo "   Please install Python 3.10+ and re-run this script."
        exit 1
    fi

    echo "   Using $SYSTEM_PYTHON to create virtual environment..."
    "$SYSTEM_PYTHON" -m venv "$VENV_DIR"
    "$VENV_PIP" install --upgrade pip
    if [ -f "$DIR/requirements.txt" ]; then
        echo "   Installing dependencies from requirements.txt..."
        "$VENV_PIP" install -r "$DIR/requirements.txt"
    fi
fi

# Fallback: if uvicorn script is missing inside venv, try installing it
if [ ! -x "$VENV_UVICORN" ]; then
    echo "⚠️  Uvicorn executable missing from virtual environment. Installing requirements..."
    "$VENV_PIP" install -r "$DIR/requirements.txt"
fi

# 2. Dependency Verification (fast import check)
MISSING_DEPS=$("$VENV_PYTHON" -c "
missing = []
for pkg in ['fastapi', 'uvicorn', 'chess', 'websockets', 'torch', 'xgboost']:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)
print(' '.join(missing))
" 2>/dev/null || echo "")

if [ -n "$MISSING_DEPS" ]; then
    echo "⚠️  Missing required packages: $MISSING_DEPS"
    echo "   Installing missing dependencies via $VENV_PIP..."
    "$VENV_PIP" install -r "$DIR/requirements.txt"
fi

# 3. Port Conflict Detection & Stale Process Handling
CONFLICT_PIDS=$(lsof -ti :"$PORT" 2>/dev/null || true)
if [ -n "$CONFLICT_PIDS" ]; then
    echo "⚠️  Port $PORT is currently occupied by existing process(es):"
    CLEANED_ALL=true
    for pid in $CONFLICT_PIDS; do
        PROC_CMD=$(ps -p "$pid" -o command= 2>/dev/null || echo "Unknown")
        echo "   -> [PID $pid] $PROC_CMD"

        # If it's a stale or previous instance of backend.api.main uvicorn, gracefully stop it
        if [[ "$PROC_CMD" =~ "backend.api.main" ]] || [[ "$PROC_CMD" =~ "uvicorn" && "$PROC_CMD" =~ "chess" ]]; then
            echo "   Stopping previous ChessMind AI backend process (PID $pid)..."
            kill -15 "$pid" 2>/dev/null || true
            sleep 1
            if kill -0 "$pid" 2>/dev/null; then
                kill -9 "$pid" 2>/dev/null || true
            fi
            echo "   PID $pid terminated."
        else
            CLEANED_ALL=false
        fi
    done

    # Re-check port availability
    STILL_OCCUPIED=$(lsof -ti :"$PORT" 2>/dev/null || true)
    if [ -n "$STILL_OCCUPIED" ]; then
        echo "❌ Error: Port $PORT is still occupied by another application."
        echo "   Please stop the conflicting process or set PORT=<port> ./start_backend.sh"
        exit 1
    fi
fi

# 4. Project-scoped environment configuration
export PYTHONPATH="$DIR"

echo "=================================================="
echo "♟  ChessMind AI Backend Service"
echo "   Python : $("$VENV_PYTHON" --version 2>&1)"
echo "   Uvicorn: $("$VENV_UVICORN" --version 2>&1)"
echo "   Host   : $HOST"
echo "   Port   : $PORT"
echo "   URL    : http://localhost:$PORT"
echo "=================================================="

exec "$VENV_UVICORN" backend.api.main:app --host "$HOST" --port "$PORT" --reload
