#!/bin/bash
# CryptoSwarm — Start all services via Docker Compose
# Usage: ./start.sh
# Stop:  ./stop.sh

set -e
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE="docker compose -f $PROJECT_DIR/infra/docker-compose.yml"

echo "========================================"
echo "  CryptoSwarm — Starting All Services"
echo "========================================"

# ── 1. Docker daemon check ────────────────────────────────────────────────────
echo "[1/3] Checking Docker..."
if ! docker info > /dev/null 2>&1; then
    echo "  ✗ Docker is not running. Start Docker Desktop first."
    exit 1
fi
echo "  ✓ Docker is running"

# ── 2. Start all containers ───────────────────────────────────────────────────
echo "[2/3] Starting containers..."
$COMPOSE up -d
echo "  ✓ Containers started"

# ── 3. Wait for health checks ─────────────────────────────────────────────────
echo "[3/3] Waiting for services to be healthy..."

wait_healthy() {
    local name="$1"
    local max=30
    local i=0
    while [ $i -lt $max ]; do
        status=$(docker inspect --format '{{.State.Health.Status}}' "$name" 2>/dev/null || echo "none")
        if [ "$status" = "healthy" ]; then
            echo "  ✓ $name healthy"
            return 0
        fi
        sleep 2
        i=$((i + 1))
    done
    echo "  ✗ $name did not become healthy in time"
    return 1
}

wait_healthy cryptoswarm-postgres
wait_healthy cryptoswarm-timescale
wait_healthy cryptoswarm-valkey
wait_healthy cryptoswarm-python
wait_healthy cryptoswarm-go
wait_healthy cryptoswarm-web

echo ""
echo "========================================"
echo "  CryptoSwarm is RUNNING"
echo "========================================"
echo ""
echo "  Dashboard  : http://localhost:3001"
echo "  Go API     : http://localhost:8080"
echo "  Python API : http://localhost:8000"
echo ""
echo "  Logs:"
echo "    All      : docker compose -f infra/docker-compose.yml logs -f"
echo "    Python   : docker logs -f cryptoswarm-python"
echo "    Go       : docker logs -f cryptoswarm-go"
echo "    Frontend : docker logs -f cryptoswarm-web"
echo ""
echo "  Stop all   : ./stop.sh"
echo ""
echo "  First Director cycle fires in ~15 seconds."
