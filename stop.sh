#!/bin/bash
# CryptoSwarm — Stop all services cleanly

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE="docker compose -f $PROJECT_DIR/infra/docker-compose.yml"

echo "Stopping CryptoSwarm..."
$COMPOSE down
echo ""
echo "All stopped. Data preserved in Docker volumes."
echo "Run ./start.sh to restart."
