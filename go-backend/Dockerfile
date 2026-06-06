# ── Stage 1: build ────────────────────────────────────────────────────────────
FROM golang:1.25-alpine AS builder

# git needed for go mod download on some deps
RUN apk add --no-cache git ca-certificates

WORKDIR /build

# Download modules before copying source — cached unless go.mod/go.sum change
COPY go.mod go.sum ./
RUN go mod download

COPY . .

# -s -w: strip debug + DWARF (shrinks binary ~30%)
# -trimpath: remove local filesystem paths from binary
# CGO_ENABLED=0: fully static, no glibc dependency
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 \
    go build -ldflags="-s -w" -trimpath -o /cryptoswarm-go ./cmd/server/

# ── Stage 2: distroless runtime ───────────────────────────────────────────────
# gcr.io/distroless/static: ~2 MB, no shell, no package manager, no setuid bins
FROM gcr.io/distroless/static-debian12:nonroot

LABEL org.opencontainers.image.title="cryptoswarm-go" \
      org.opencontainers.image.description="CryptoSwarm Go API gateway — REST + WebSocket + gRPC client" \
      org.opencontainers.image.vendor="CryptoSwarm" \
      com.cryptoswarm.service="go-gateway" \
      com.cryptoswarm.tier="app"

COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /cryptoswarm-go /cryptoswarm-go

# nonroot is UID 65532 in distroless
USER nonroot:nonroot

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["/cryptoswarm-go", "-healthcheck"]

EXPOSE 8080

ENTRYPOINT ["/cryptoswarm-go"]
