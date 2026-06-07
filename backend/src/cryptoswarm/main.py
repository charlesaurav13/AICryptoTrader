import asyncio
import logging
import os
import signal as _signal
import uvicorn

from cryptoswarm.config.settings import get_settings
from cryptoswarm.bus.client import BusClient
from cryptoswarm.bus.messages import SystemHeartbeat
from cryptoswarm.feed.rest_client import BinanceRestClient
from cryptoswarm.feed.handler import FrameHandler
from cryptoswarm.feed.ws_client import FeedManager
from cryptoswarm.storage.timescale import TimescaleWriter
from cryptoswarm.storage.postgres import PostgresWriter
from cryptoswarm.storage.subscriber import StorageSubscriber
from cryptoswarm.storage.decisions import DecisionWriter
from cryptoswarm.papertrade.engine import PaperTradeEngine
from cryptoswarm.agents.llm import LLMClient, make_llm_for_agent
from cryptoswarm.agents.quant import QuantAgent
from cryptoswarm.agents.risk_agent import RiskAgent
from cryptoswarm.agents.sentiment import SentimentAgent
from cryptoswarm.agents.portfolio import PortfolioAgent
from cryptoswarm.agents.director import DirectorAgent
from cryptoswarm.agents.ml_agent import MLAgent
from cryptoswarm.agents.reward_computer import RewardComputer
from cryptoswarm.ml.features import FeatureEngine, FEATURE_SIZE
from cryptoswarm.ml.kronos_model import KronosModel
from cryptoswarm.ml.ppo_policy import PPOPolicy
from cryptoswarm.ml.reward import RewardConfig
from cryptoswarm.learning.prompt_store import PromptStore
from cryptoswarm.learning.prompt_evolution import PromptEvolutionEngine
from cryptoswarm.scraper.runner import ScraperRunner
from cryptoswarm.api.app import create_app
from cryptoswarm.api import deps
from cryptoswarm.grpc_server import serve_grpc

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)


async def heartbeat_loop(bus: BusClient, interval_s: int) -> None:
    while True:
        await bus.publish("system.heartbeat", SystemHeartbeat(process_id=os.getpid()))
        await asyncio.sleep(interval_s)


async def main() -> None:
    cfg = get_settings()
    logger.info("Starting CryptoSwarm Phase 3 (paper_trading=%s)", cfg.paper_trading)

    # --- Core infrastructure ---
    bus = BusClient(cfg.valkey_url)
    await bus.connect()

    ts_writer = TimescaleWriter(cfg.timescale_dsn)
    await ts_writer.connect()
    pg_writer = PostgresWriter(cfg.postgres_dsn)
    await pg_writer.connect()

    rest = BinanceRestClient(cfg.binance_api_key, cfg.binance_api_secret, cfg.binance_testnet)
    await rest.connect()

    decisions_writer = DecisionWriter(cfg.postgres_dsn)
    await decisions_writer.connect()

    # --- ML / learning components ---
    features       = FeatureEngine(ts=ts_writer, pg=pg_writer)
    kronos_model   = KronosModel()                           # lazy-loads Kronos-base on first predict
    ppo_policy     = PPOPolicy(state_size=FEATURE_SIZE)
    reward_cfg     = RewardConfig()
    prompt_store   = PromptStore(pg=pg_writer)

    # --- Feed + storage ---
    handler     = FrameHandler(bus)
    feed        = FeedManager(cfg, handler, rest)
    storage_sub = StorageSubscriber(bus, ts_writer, pg_writer)
    engine      = PaperTradeEngine(bus, cfg)

    # --- Agents ---
    quant_agent     = QuantAgent(bus=bus, ts=ts_writer, llm=make_llm_for_agent("quant", cfg))
    risk_agent      = RiskAgent(bus=bus, llm=make_llm_for_agent("risk", cfg), settings=cfg)
    sentiment_agent = SentimentAgent(bus=bus, pg=pg_writer)
    portfolio_agent = PortfolioAgent(bus=bus, llm=make_llm_for_agent("portfolio", cfg), settings=cfg)
    ml_agent        = MLAgent(
        bus=bus, features=features,
        kronos=kronos_model, ppo=ppo_policy,
        pg=pg_writer,
    )
    reward_computer = RewardComputer(
        bus=bus, pg=pg_writer, ppo=ppo_policy,
        features=features, reward_config=reward_cfg,
    )
    director = DirectorAgent(
        bus=bus,
        llm=make_llm_for_agent("director", cfg),
        decisions=decisions_writer,
        settings=cfg,
        prompt_store=prompt_store,
    )

    # --- Batch learning loops ---
    evolution_engine = PromptEvolutionEngine(
        pg=pg_writer,
        llm=make_llm_for_agent("director", cfg),
        prompt_store=prompt_store,
        interval_s=cfg.prompt_evolution_interval_s,
        lookback=cfg.prompt_evolution_lookback,
    )
    scraper = ScraperRunner(pg=pg_writer, bus=bus, settings=cfg)

    # --- API ---
    deps.set_deps(bus=bus, pg=pg_writer, ts=ts_writer, engine=engine)
    app    = create_app()
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=8000, log_level="info"))

    tasks = [
        asyncio.create_task(feed.run(),                name="feed"),
        asyncio.create_task(storage_sub.run(),          name="storage"),
        asyncio.create_task(engine.run(),               name="engine"),
        asyncio.create_task(quant_agent.run(),          name="quant_agent"),
        asyncio.create_task(risk_agent.run(),           name="risk_agent"),
        asyncio.create_task(sentiment_agent.run(),      name="sentiment_agent"),
        asyncio.create_task(portfolio_agent.run(),      name="portfolio_agent"),
        asyncio.create_task(ml_agent.run(),             name="ml_agent"),
        asyncio.create_task(reward_computer.run(),      name="reward_computer"),
        asyncio.create_task(director.run(),             name="director"),
        asyncio.create_task(evolution_engine.run(),     name="prompt_evolution"),
        asyncio.create_task(scraper.run(),              name="scraper"),
        asyncio.create_task(
            heartbeat_loop(bus, cfg.risk.heartbeat_interval_s), name="heartbeat"
        ),
        asyncio.create_task(server.serve(),             name="api"),
        asyncio.create_task(serve_grpc(engine, bus, port=50051), name="grpc_server"),
    ]

    loop = asyncio.get_running_loop()
    for sig in (_signal.SIGTERM, _signal.SIGINT):
        loop.add_signal_handler(sig, lambda: [t.cancel() for t in tasks])

    logger.info("All 15 tasks started. CryptoSwarm Phase 3 running.")
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Shutdown initiated")
    finally:
        await bus.close()
        await ts_writer.close()
        await pg_writer.close()
        await decisions_writer.close()
        await rest.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
