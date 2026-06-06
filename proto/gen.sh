#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Generate Python
cd "$PROJECT_ROOT/backend"
source .venv/bin/activate
pip install grpcio-tools==1.81.0 -q
python -m grpc_tools.protoc \
  -I "$SCRIPT_DIR" \
  --python_out="src/cryptoswarm/proto" \
  --grpc_python_out="src/cryptoswarm/proto" \
  "$SCRIPT_DIR/cryptoswarm.proto"

# Generate Go
cd "$PROJECT_ROOT/go-backend"
export PATH="$PATH:$(go env GOPATH)/bin"
protoc \
  -I "$SCRIPT_DIR" \
  --go_out=proto --go_opt=paths=source_relative \
  --go-grpc_out=proto --go-grpc_opt=paths=source_relative \
  "$SCRIPT_DIR/cryptoswarm.proto"

echo "Codegen complete."
