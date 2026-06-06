# ── Stage 1: install production deps ─────────────────────────────────────────
FROM node:22-alpine AS deps

RUN apk add --no-cache libc6-compat

WORKDIR /app
COPY package.json package-lock.json ./
# ci is faster and deterministic; --omit=dev skips devDependencies
RUN npm ci --omit=dev

# ── Stage 2: build ────────────────────────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app
# Need all deps (including devDeps) for the build step
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# next.config.ts has output: "standalone" — build emits a self-contained server
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ── Stage 3: minimal runtime ──────────────────────────────────────────────────
# standalone mode ships only the files Next.js actually needs at runtime —
# roughly 100 MB vs 1+ GB for a full node_modules copy.
FROM node:22-alpine AS runner

RUN apk add --no-cache dumb-init

WORKDIR /app

LABEL org.opencontainers.image.title="cryptoswarm-web" \
      org.opencontainers.image.description="CryptoSwarm Next.js trading dashboard" \
      org.opencontainers.image.vendor="CryptoSwarm" \
      com.cryptoswarm.service="web-frontend" \
      com.cryptoswarm.tier="app"

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Unprivileged user
RUN addgroup -S -g 1001 nextjs \
 && adduser  -S -u 1001 -G nextjs nextjs

COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static     ./.next/static
COPY --from=builder --chown=nextjs:nextjs /app/public           ./public

USER nextjs

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD wget -qO- http://localhost:3000/ || exit 1

EXPOSE 3000

# dumb-init reaps zombie processes and forwards signals correctly
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "server.js"]
