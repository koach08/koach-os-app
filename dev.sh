#!/bin/bash
# Koach OS v2 — Next.js + FastAPI 同時起動
# Usage: ./dev.sh

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🚀 Koach OS v2 — Starting development servers..."
echo "   Backend:  http://localhost:8000"
echo "   Frontend: http://localhost:3000"
echo ""

# Kill existing processes on ports 8000 and 3000
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true

# Activate venv if exists
if [ -f "$PROJECT_DIR/venv/bin/activate" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
fi

# Start backend
cd "$PROJECT_DIR/backend"
uvicorn main:app --reload --port 8000 &
BACKEND_PID=$!

# Start frontend
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo "PIDs: backend=$BACKEND_PID, frontend=$FRONTEND_PID"
echo "Press Ctrl+C to stop both servers."

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM

wait
