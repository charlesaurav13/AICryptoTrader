# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

RUN pip install --no-cache-dir uv==0.5.29

WORKDIR /build
COPY pyproject.toml .

# CPU-only torch first (largest dep — own layer for cache efficiency).
# The whl/cpu index strips CUDA, saving ~2 GB.
RUN uv pip install --system --no-cache \
    torch --index-url https://download.pytorch.org/whl/cpu

# Remaining runtime deps (no [dev] extras)
RUN uv pip install --system --no-cache .

# ── Stage 2: hardened runtime ─────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Unprivileged user — no login shell, no writable home
RUN groupadd -r -g 1001 cryptoswarm \
 && useradd  -r -u 1001 -g cryptoswarm -s /usr/sbin/nologin cryptoswarm

# Copy installed packages from builder (build tools not included)
COPY --from=builder /usr/local/lib/python3.12 /usr/local/lib/python3.12
COPY --from=builder /usr/local/bin             /usr/local/bin

WORKDIR /app
COPY --chown=cryptoswarm:cryptoswarm src/ src/

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1

USER cryptoswarm

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

EXPOSE 8000 50051

CMD ["python3", "-m", "cryptoswarm.main"]
