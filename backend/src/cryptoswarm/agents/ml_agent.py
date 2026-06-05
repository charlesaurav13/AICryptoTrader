"""MLAgent — 5th signal agent. Uses Kronos-base + PPO to produce MLSignal."""
from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from cryptoswarm.bus.client import BusClient
from cryptoswarm.bus.messages import AnalyzeRequest, MLSignal

if TYPE_CHECKING:
    from cryptoswarm.ml.features import FeatureEngine
    from cryptoswarm.ml.kronos_model import KronosModel
    from cryptoswarm.ml.ppo_policy import PPOPolicy
    from cryptoswarm.storage.postgres import PostgresWriter

logger = logging.getLogger(__name__)


class MLAgent:
    def __init__(
        self,
        bus: BusClient,
        features: "FeatureEngine",
        kronos: "KronosModel",
        ppo: "PPOPolicy",
        pg: "PostgresWriter",
    ) -> None:
        self._bus = bus
        self._features = features
        self._kronos = kronos
        self._ppo = ppo
        self._pg = pg

    async def run(self) -> None:
        async for _, data in self._bus.psubscribe("agent.analyze.*"):
            req = AnalyzeRequest.model_validate_json(data)
            try:
                await self._handle(req)
            except Exception as exc:
                logger.error("MLAgent error for %s: %s", req.symbol, exc)

    async def _handle(self, req: AnalyzeRequest) -> None:
        try:
            # Raw klines for Kronos (512 bars of 1m data)
            klines = await self._features._ts.fetch_klines(req.symbol, limit=512)
            # Feature vector for PPO size adjustment
            feat_vec = await self._features.build(req.symbol)
        except Exception as exc:
            logger.warning("MLAgent: data fetch failed for %s: %s", req.symbol, exc)
            await self._publish_neutral(req)
            return

        try:
            # Kronos is CPU/GPU-bound — run in thread to avoid blocking the event loop
            regime, direction, short_dir, kronos_conf = await asyncio.to_thread(
                self._kronos.predict, klines
            )
            size_adj, _ppo_conf = self._ppo.predict(feat_vec)  # confidence is Kronos-derived
        except Exception as exc:
            logger.warning("MLAgent: model inference failed for %s: %s", req.symbol, exc)
            await self._publish_neutral(req, reason="model inference failed — neutral fallback")
            return

        confidence = round(kronos_conf, 4)

        reasoning = (
            f"Kronos-base: regime={regime} dir={direction} "
            f"short={short_dir} conf={kronos_conf:.2f} | "
            f"PPO: size_adj={size_adj}"
        )

        msg = MLSignal(
            symbol=req.symbol,
            correlation_id=req.correlation_id,
            regime_pred=regime,
            direction_pred=direction,
            short_direction=short_dir,
            size_adjustment=size_adj,
            confidence=confidence,
            reasoning=reasoning,
        )
        await self._bus.publish(f"agent.result.ml.{req.symbol}", msg)

        await self._pg.insert_ml_signal(
            symbol=req.symbol,
            regime_pred=regime,
            direction_pred=direction,
            short_direction=short_dir,
            confidence=confidence,
            size_adjustment=size_adj,
            model_version="kronos-base",
        )
        logger.info(
            "MLAgent: %s regime=%s dir=%s short=%s adj=%s conf=%.2f",
            req.symbol, regime, direction, short_dir, size_adj, confidence,
        )

    async def _publish_neutral(self, req: AnalyzeRequest, reason: str = "feature build failed — neutral fallback") -> None:
        msg = MLSignal(
            symbol=req.symbol,
            correlation_id=req.correlation_id,
            regime_pred="ranging",
            direction_pred="up",
            short_direction="up",
            size_adjustment="hold",
            confidence=0.0,
            reasoning=reason,
        )
        await self._bus.publish(f"agent.result.ml.{req.symbol}", msg)
        try:
            await self._pg.insert_ml_signal(
                symbol=req.symbol,
                regime_pred="ranging",
                direction_pred="up",
                short_direction="up",
                confidence=0.0,
                size_adjustment="hold",
                model_version="neutral_fallback",
            )
        except Exception as exc:
            logger.warning("MLAgent: failed to persist neutral signal for %s: %s", req.symbol, exc)
