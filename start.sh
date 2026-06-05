#!/bin/bash
# CryptoSwarm Phase 3 — Paper Trading Startup Script
# Usage: ./start.sh
# Stop:  ./stop.sh

set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="/tmp/cryptoswarm.log"

echo "========================================"
echo "  CryptoSwarm Phase 3 — Starting Up"
echo "========================================"

# ── 1. Check Ollama is running ────────────────────────────────────────────────
echo "[1/4] Checking Ollama..."
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "  ✗ Ollama is not running."
    echo "    Start it with: ollama serve"
    exit 1
fi

# Warm up qwen2.5:7b (loads model into GPU memory so first agent cycle is fast)
echo "  → Warming up qwen2.5:7b..."
curl -s http://localhost:11434/api/generate \
    -d '{"model":"qwen2.5:7b","prompt":"hi","stream":false,"options":{"num_predict":1}}' \
    > /dev/null 2>&1 &
WARM_PID=$!
echo "  ✓ Model warming in background (PID $WARM_PID)"

# ── 2. Start Docker infrastructure ───────────────────────────────────────────
echo "[2/4] Starting Docker infrastructure (Valkey, TimescaleDB, Postgres)..."
docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" up -d valkey timescale postgres

echo "  → Waiting for databases to be healthy..."
until docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" \
    exec -T postgres pg_isready -U postgres > /dev/null 2>&1; do
    sleep 2
done
until docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" \
    exec -T timescale pg_isready -U postgres > /dev/null 2>&1; do
    sleep 2
done
echo "  ✓ All databases healthy"

# ── 3. Wait for model warm-up ─────────────────────────────────────────────────
echo "[3/4] Waiting for model warm-up..."
wait $WARM_PID 2>/dev/null || true
echo "  ✓ qwen2.5:7b ready"

# ── 4. Start CryptoSwarm backend ─────────────────────────────────────────────
echo "[4/4] Starting CryptoSwarm backend..."
cd "$PROJECT_DIR"
source backend/.venv/bin/activate

nohup python3 -m cryptoswarm.main > "$LOG_FILE" 2>&1 &
BACKEND_PID=$!
echo $BACKEND_PID > /tmp/cryptoswarm.pid

sleep 5
if kill -0 $BACKEND_PID 2>/dev/null; then
    echo "  ✓ Backend running (PID $BACKEND_PID)"
else
    echo "  ✗ Backend failed to start. Check logs: tail -50 $LOG_FILE"
    exit 1
fi

echo ""
echo "========================================"
echo "  CryptoSwarm is RUNNING"
echo "========================================"
echo ""
echo "  Dashboard API : http://localhost:8000"
echo "  Live logs     : tail -f $LOG_FILE"
echo "  Stop          : ./stop.sh"
echo ""
echo "  First Director cycle fires in ~15 seconds."
echo "  Watch for: DirectorAgent: BTCUSDT action=buy/sell/hold"
echo ""
