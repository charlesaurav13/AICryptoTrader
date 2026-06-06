#!/bin/bash
# CryptoSwarm — Stop all services cleanly

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Stopping CryptoSwarm..."

stop_pid() {
    local label="$1" pidfile="$2" fallback="$3"
    if [ -f "$pidfile" ]; then
        PID=$(cat "$pidfile")
        kill "$PID" 2>/dev/null && echo "  ✓ $label stopped (PID $PID)" || echo "  · $label already gone"
        rm -f "$pidfile"
    elif [ -n "$fallback" ]; then
        pkill -f "$fallback" 2>/dev/null && echo "  ✓ $label stopped" || true
    fi
}

stop_pid "Next.js"       /tmp/cryptoswarm-next.pid   "next dev"
stop_pid "Go gateway"    /tmp/cryptoswarm-go.pid      "cryptoswarm-go"
stop_pid "Python backend" /tmp/cryptoswarm-python.pid "cryptoswarm.main"

# Unload Ollama models from GPU memory
ollama stop qwen2.5:7b 2>/dev/null && echo "  ✓ qwen2.5:7b unloaded" || true
ollama stop qwen3:8b   2>/dev/null && echo "  ✓ qwen3:8b unloaded"   || true

# Docker infrastructure
docker compose -f "$PROJECT_DIR/infra/docker-compose.yml" down
echo "  ✓ Docker infrastructure stopped"

echo ""
echo "All stopped. Data preserved in Docker volumes."
echo "Run ./start.sh to restart."
