#!/bin/bash
# CryptoSwarm — Full-stack startup: infra → Python → Go → Next.js
# Usage: ./start.sh
# Stop:  ./stop.sh

set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_PYTHON="$PROJECT_DIR/logs/python.log"
LOG_GO="$PROJECT_DIR/logs/go.log"
LOG_NEXT="$PROJECT_DIR/logs/nextjs.log"

mkdir -p "$PROJECT_DIR/logs"

echo "========================================"
echo "  CryptoSwarm — Starting All Services"
echo "========================================"

# ── 1. Check Ollama ───────────────────────────────────────────────────────────
echo "[1/6] Checking Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  ✗ Ollama is not running. Start it with: ollama serve"
    exit 1
fi

echo "  → Warming up qwen2.5:7b..."
curl -s http://localhost:11434/api/generate \
    -d '{"model":"qwen2.5:7b","prompt":"hi","stream":false,"options":{"num_predict":1}}' \
    > /dev/null 2>&1 &
WARM_PID=$!
echo "  ✓ Model warming in background (PID $WARM_PID)"

# ── 2. Docker infrastructure ──────────────────────────────────────────────────
echo "[2/6] Starting Docker infrastructure (Valkey, TimescaleDB, Postgres)..."
docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" up -d valkey timescale postgres

echo "  → Waiting for databases to be healthy..."
until docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" \
    exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do sleep 2; done
until docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" \
    exec -T timescale pg_isready -U postgres > /dev/null 2>&1; do sleep 2; done
echo "  ✓ All databases healthy"

# ── 3. Wait for model warm-up ─────────────────────────────────────────────────
echo "[3/6] Waiting for model warm-up..."
wait $WARM_PID 2>/dev/null || true
echo "  ✓ qwen2.5:7b ready"

# ── 4. Python backend (gRPC + REST + agents) ──────────────────────────────────
echo "[4/6] Starting Python backend..."
cd "$PROJECT_DIR"
source backend/.venv/bin/activate

nohup python3 -m cryptoswarm.main > "$LOG_PYTHON" 2>&1 &
PYTHON_PID=$!
echo $PYTHON_PID > /tmp/cryptoswarm-python.pid

sleep 5
if kill -0 $PYTHON_PID 2>/dev/null; then
    echo "  ✓ Python backend running (PID $PYTHON_PID)"
else
    echo "  ✗ Python backend failed. Check: tail -50 $LOG_PYTHON"
    exit 1
fi

# ── 5. Go API gateway ─────────────────────────────────────────────────────────
echo "[5/6] Building and starting Go API gateway..."
cd "$PROJECT_DIR/go-backend"
go build -o /tmp/cryptoswarm-go ./cmd/server/
echo "  ✓ Go binary built"

cd "$PROJECT_DIR"
set -a; source .env; set +a
nohup /tmp/cryptoswarm-go > "$LOG_GO" 2>&1 &
GO_PID=$!
echo $GO_PID > /tmp/cryptoswarm-go.pid

sleep 2
if kill -0 $GO_PID 2>/dev/null; then
    echo "  ✓ Go gateway running (PID $GO_PID) on :${GO_PORT:-8080}"
else
    echo "  ✗ Go gateway failed. Check: tail -50 $LOG_GO"
    exit 1
fi

# ── 6. Next.js frontend ───────────────────────────────────────────────────────
echo "[6/6] Starting Next.js frontend..."
cd "$PROJECT_DIR/frontend"
nohup npm run dev > "$LOG_NEXT" 2>&1 &
NEXT_PID=$!
echo $NEXT_PID > /tmp/cryptoswarm-next.pid

sleep 4
if kill -0 $NEXT_PID 2>/dev/null; then
    echo "  ✓ Next.js running (PID $NEXT_PID) on :3000"
else
    echo "  ✗ Next.js failed. Check: tail -50 $LOG_NEXT"
    exit 1
fi

echo ""
echo "========================================"
echo "  CryptoSwarm is RUNNING"
echo "========================================"
echo ""
echo "  Dashboard  : http://localhost:3000"
echo "  Go API     : http://localhost:${GO_PORT:-8080}"
echo "  Python API : http://localhost:8000"
echo ""
echo "  Logs:"
echo "    Python  : tail -f $LOG_PYTHON"
echo "    Go      : tail -f $LOG_GO"
echo "    Next.js : tail -f $LOG_NEXT"
echo ""
echo "  Stop all  : ./stop.sh"
echo ""
echo "  First Director cycle fires in ~15 seconds."
