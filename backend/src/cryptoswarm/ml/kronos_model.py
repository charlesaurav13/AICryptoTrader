"""KronosModel — zero-shot OHLCV forecasting via pretrained Kronos-base.

Replaces XGBoostModel + LSTMModel in MLAgent. No local training required.
Model is downloaded from HuggingFace on first use (~400MB).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

_TOKENIZER_HF = "NeoQuasar/Kronos-Tokenizer-base"
_MODEL_HF = "NeoQuasar/Kronos-base"

# Prediction horizons (in bars) for regime and short-term direction
_LONG_HORIZON = 60   # bars ahead for regime + main direction
_SHORT_HORIZON = 15  # bars ahead for short_direction


class KronosModel:
    """Wraps KronosPredictor. Predict returns (regime, direction, short_direction, confidence)."""

    def __init__(
        self,
        pred_len: int = _LONG_HORIZON,
        max_context: int = 512,
        verbose: bool = False,
    ) -> None:
        self._pred_len = pred_len
        self._max_context = max_context
        self._verbose = verbose
        self._predictor = None  # lazy-loaded on first predict()

    def _ensure_loaded(self) -> None:
        if self._predictor is not None:
            return
        logger.info("KronosModel: loading Kronos-base from HuggingFace (first use)...")
        from cryptoswarm.ml.kronos_vendor import Kronos, KronosPredictor, KronosTokenizer
        tokenizer = KronosTokenizer.from_pretrained(_TOKENIZER_HF)
        model = Kronos.from_pretrained(_MODEL_HF)
        self._predictor = KronosPredictor(model, tokenizer, max_context=self._max_context)
        logger.info("KronosModel: loaded")

    def predict(
        self,
        klines: list[dict],
        interval_minutes: int = 1,
    ) -> tuple[
        Literal["trending_up", "trending_down", "ranging", "volatile"],
        Literal["up", "down"],
        Literal["up", "down"],
        float,
    ]:
        """
        klines: list of {'open','high','low','close','volume'} dicts (chronological).
        interval_minutes: candle interval (1 for 1m bars from fetch_klines).
        Returns: (regime, direction, short_direction, confidence).
        """
        if not klines:
            return "ranging", "up", "up", 0.0

        self._ensure_loaded()

        n = len(klines)
        now = pd.Timestamp.now(tz="UTC").floor(f"{interval_minutes}min")
        x_timestamps = pd.date_range(
            end=now, periods=n, freq=f"{interval_minutes}min", tz="UTC"
        )
        y_timestamps = pd.date_range(
            start=x_timestamps[-1] + pd.Timedelta(minutes=interval_minutes),
            periods=self._pred_len,
            freq=f"{interval_minutes}min",
            tz="UTC",
        )

        df = pd.DataFrame(klines)[["open", "high", "low", "close", "volume"]]
        avg_price = df[["open", "high", "low", "close"]].mean(axis=1)
        df["amount"] = df["volume"] * avg_price

        try:
            pred_df = self._predictor.predict(
                df=df,
                x_timestamp=x_timestamps,
                y_timestamp=y_timestamps,
                pred_len=self._pred_len,
                T=1.0,
                top_p=0.9,
                sample_count=1,
                verbose=self._verbose,
            )
        except Exception as exc:
            logger.warning("KronosModel.predict error: %s", exc)
            return "ranging", "up", "up", 0.0

        return self._derive_signals(float(klines[-1]["close"]), pred_df)

    def _derive_signals(
        self,
        current_close: float,
        pred_df: pd.DataFrame,
    ) -> tuple[str, str, str, float]:
        closes = pred_df["close"].values.astype(float)
        if len(closes) == 0:
            return "ranging", "up", "up", 0.0

        # Direction over full horizon
        direction: Literal["up", "down"] = "up" if closes[-1] > current_close else "down"

        # Short-term direction over first _SHORT_HORIZON bars
        short_idx = min(_SHORT_HORIZON - 1, len(closes) - 1)
        short_direction: Literal["up", "down"] = "up" if closes[short_idx] > current_close else "down"

        # Regime from slope + volatility of predicted closes
        returns = np.diff(closes) / (np.abs(closes[:-1]) + 1e-9)
        slope = (closes[-1] - closes[0]) / (np.abs(closes[0]) + 1e-9)
        volatility = float(np.std(returns)) if len(returns) > 0 else 0.0

        if volatility > 0.012:
            regime: Literal["trending_up", "trending_down", "ranging", "volatile"] = "volatile"
        elif abs(slope) < 0.002:
            regime = "ranging"
        elif slope > 0:
            regime = "trending_up"
        else:
            regime = "trending_down"

        # Confidence: directional consistency × magnitude
        changes = np.diff(closes)
        if len(changes) > 0:
            consistency = float(np.mean(changes > 0)) if direction == "up" else float(np.mean(changes < 0))
        else:
            consistency = 0.5
        magnitude = min(abs(closes[-1] - current_close) / (abs(current_close) + 1e-9) * 20.0, 1.0)
        confidence = round(0.6 * consistency + 0.4 * magnitude, 4)

        return regime, direction, short_direction, confidence
