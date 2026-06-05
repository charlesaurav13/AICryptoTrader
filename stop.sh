#!/bin/bash
# CryptoSwarm — Stop everything cleanly

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Stopping CryptoSwarm..."

# Stop backend
if [ -f /tmp/cryptoswarm.pid ]; then
    PID=$(cat /tmp/cryptoswarm.pid)
    kill "$PID" 2>/dev/null && echo "  ✓ Backend stopped (PID $PID)"
    rm -f /tmp/cryptoswarm.pid
else
    pkill -f "cryptoswarm.main" 2>/dev/null && echo "  ✓ Backend stopped" || true
fi

# Unload Ollama models from memory
ollama stop qwen2.5:7b 2>/dev/null && echo "  ✓ qwen2.5:7b unloaded" || true
ollama stop qwen3:8b   2>/dev/null && echo "  ✓ qwen3:8b unloaded"   || true

# Stop Docker infrastructure
docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" down
echo "  ✓ Docker infrastructure stopped"

echo ""
echo "All stopped. Data is preserved in Docker volumes."
echo "Run ./start.sh to restart."
