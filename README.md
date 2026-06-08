# CryptoSwarm

A multi-agent AI system for paper trading crypto futures. Five specialized agents analyze the market independently every 60 seconds; a Director agent synthesizes their views into a final decision. All trades are simulated — no real money.

---

## Architecture

```
                      ┌─────────────────────────────┐
                      │        Director Agent        │
                      │  (OpenRouter / deepseek-v3)  │
                      └──────────┬──────────────────┘
              ┌───────────┬──────┴──────┬───────────┬───────────┐
              ▼           ▼             ▼           ▼           ▼
          Quant         Risk       Sentiment    Portfolio      ML
          Agent        Agent        Agent        Agent      (Kronos)
         (LLM)        (LLM)     (FNG + LLM)    (LLM)   (HuggingFace)
              └───────────┴──────┬──────┴───────────┴───────────┘
                                 ▼
                       PaperTradeEngine
                     (SL / TP / max-hold)
                                 ▼
                  ┌──────────────┴─────────────┐
                  │          Valkey             │  ← message bus
                  └──────────────┬─────────────┘
           ┌──────────────┬──────┴──────┬───────────────┐
           ▼              ▼             ▼               ▼
       FastAPI         gRPC         TimescaleDB     PostgreSQL
      (REST/SSE)      server       (OHLCV + marks)  (trades, decisions)
           └──────────────┴──────┬──────┘
                                 ▼
                         Go API gateway
                         (Gin + auth)
                                 ▼
                       Next.js 15 dashboard
```

**Stack**

| Layer | Technology |
|---|---|
| Agents + engine | Python 3.12, FastAPI, asyncio, gRPC |
| API gateway | Go 1.23, Gin |
| Frontend | Next.js 15 (App Router), Tailwind CSS v4 |
| Message bus | Valkey 8 (Redis-compatible pub/sub) |
| Databases | PostgreSQL 16 (trades) + TimescaleDB (market data) |
| Market data | Binance USDM Futures WebSocket (testnet) |
| LLM provider | OpenRouter (deepseek/deepseek-chat-v3-0324) |
| ML model | NeoQuasar/Kronos-base (HuggingFace safetensors) |

---

## Agents

| Agent | Role |
|---|---|
| **Quant** | Technical analysis — regime detection, RSI, EMA, ATR, volume strength |
| **Risk** | Position sizing via Kelly criterion, max-loss caps, circuit-breaker |
| **Sentiment** | Fear & Greed Index + news-headline LLM scoring |
| **Portfolio** | Open-position accounting, correlation checks, hard position-cap guard |
| **ML (Kronos)** | Kronos-base transformer — regime + direction + PPO size adjustment |
| **Director** | Synthesizes all five results; requires ≥ 0.65 confidence to trade |

A signal is only published when **all 5 agents respond within the timeout** and the Director's confidence clears the threshold.

---

## Paper Trading Rules

- Starting balance: **$1,000 USDT**
- Max leverage: **5×**
- Max open positions: **5**
- Per-trade size: decided by Kelly / Director (≤ $30 default)
- Stop-loss: 2 % from entry
- Take-profit: 4 % from entry
- Max hold time: **6 hours** — force-closed at mark price if exceeded
- 5-minute cooldown per symbol after any signal

---

## Getting Started

### Prerequisites

- Docker Desktop 4.x
- An `.env` file at the project root (see `.env.example`)

```
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
BINANCE_TESTNET=true

OPENROUTER_API_KEY=...

DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=...
SECRET_KEY=...          # any random 32-char string
```

### Run

```bash
# Build images and start all services
docker compose -f infra/docker-compose.yml up -d --build

# Stream logs
docker compose -f infra/docker-compose.yml logs -f python-backend
```

Or use the convenience scripts:

```bash
./start.sh   # builds & starts everything
./stop.sh    # stops all containers
```

### Dashboard

| URL | What |
|---|---|
| `http://localhost:3000` | Next.js dashboard (login required) |
| `http://localhost:8080` | Go API gateway |
| `http://localhost:8000` | Python FastAPI (health, SSE, gRPC) |

Default credentials are whatever you set in `.env` (`DASHBOARD_USERNAME` / `DASHBOARD_PASSWORD`).

---

## Project Layout

```
.
├── backend/                 # Python — agents, engine, API
│   └── src/cryptoswarm/
│       ├── agents/          # Director, Quant, Risk, Sentiment, Portfolio, ML
│       ├── papertrade/      # PaperTradeEngine, Account, position lifecycle
│       ├── feed/            # Binance WebSocket + REST client
│       ├── bus/             # Valkey pub/sub client
│       ├── storage/         # PostgreSQL + TimescaleDB writers
│       └── api/             # FastAPI routes + gRPC server
├── go-backend/              # Go — API gateway, auth, DB queries
├── frontend/                # Next.js 15 dashboard
├── infra/                   # docker-compose.yml, DB migrations
└── proto/                   # Protobuf definitions (shared)
```

---

## License

MIT
