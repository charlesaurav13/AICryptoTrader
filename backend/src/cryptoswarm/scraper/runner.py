"""ScraperRunner — fetches crypto news via OpenRouter (Perplexity Sonar) every 30 minutes."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from cryptoswarm.scraper.searcher import OpenRouterNewsSearcher
from cryptoswarm.scraper.scorer import OpenRouterScorer
from cryptoswarm.scraper.writer import NewsWriter

if TYPE_CHECKING:
    from cryptoswarm.bus.client import BusClient
    from cryptoswarm.config.settings import Settings
    from cryptoswarm.storage.postgres import PostgresWriter

logger = logging.getLogger(__name__)


class ScraperRunner:
    def __init__(self, pg: "PostgresWriter", bus: "BusClient", settings: "Settings") -> None:
        self._pg = pg
        self._bus = bus
        self._cfg = settings

        api_key = settings.openrouter_api_key
        symbols = settings.symbol_list

        self._searcher = OpenRouterNewsSearcher(
            api_key=api_key,
            model=settings.scraper_search_model,
            symbols=symbols,
        )
        self._scorer = OpenRouterScorer(
            api_key=api_key,
            model=settings.scraper_score_model,
            symbols=symbols,
        )
        self._writer = NewsWriter(
            pg=pg,
            bus=bus,
            min_relevance=settings.scraper_min_relevance,
            model=settings.scraper_score_model,
        )

    async def run(self) -> None:
        while True:
            await self._scrape_all()
            await asyncio.sleep(self._cfg.scraper_interval_s)

    async def _scrape_all(self) -> None:
        symbols = self._cfg.symbol_list
        logger.info("ScraperRunner: searching news for %d symbols via Perplexity Sonar", len(symbols))

        # Search all symbols in parallel
        searches = await asyncio.gather(
            *[self._searcher.search_symbol(sym) for sym in symbols],
            return_exceptions=True,
        )

        total_articles = 0
        errors = 0
        for sym, result in zip(symbols, searches):
            if isinstance(result, Exception):
                logger.warning("ScraperRunner: %s search error — %s", sym, result)
                errors += 1
                continue
            for article in result:
                try:
                    scores = await self._scorer.score(
                        title=article["title"],
                        body=article["body"],
                    )
                    await self._writer.write(
                        source=f"perplexity_sonar_{sym.lower()}",
                        url=article["url"],
                        title=article["title"],
                        body=article["body"],
                        scores=scores,
                    )
                    total_articles += 1
                except Exception as exc:
                    logger.warning("ScraperRunner: write error for %s — %s", sym, exc)

        logger.info(
            "ScraperRunner: cycle complete — %d articles written, %d symbol errors",
            total_articles, errors,
        )
