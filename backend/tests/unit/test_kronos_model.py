"""Tests for KronosModel — mocks KronosPredictor, tests signal derivation."""
import numpy as np
import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from cryptoswarm.ml.kronos_model import KronosModel


def _fake_klines(n: int = 100, base_price: float = 65000.0) -> list[dict]:
    import random
    random.seed(42)
    price = base_price
    rows = []
    for _ in range(n):
        price *= (1 + random.uniform(-0.001, 0.001))
        rows.append({
            "open": price * 0.999, "high": price * 1.001,
            "low": price * 0.998, "close": price,
            "volume": random.uniform(100, 500),
        })
    return rows


def _make_pred_df(closes: list[float]) -> pd.DataFrame:
    """Build a minimal pred_df with just close prices."""
    n = len(closes)
    return pd.DataFrame({
        "open":   [c * 0.999 for c in closes],
        "high":   [c * 1.001 for c in closes],
        "low":    [c * 0.998 for c in closes],
        "close":  closes,
        "volume": [100.0] * n,
        "amount": [c * 100.0 for c in closes],
    })


# ─── _derive_signals tests (no model loading) ───────────────────────────────

def test_derive_uptrend():
    model = KronosModel.__new__(KronosModel)
    closes = [100.0 + i * 0.5 for i in range(60)]  # steady rise
    regime, direction, short_dir, conf = model._derive_signals(100.0, _make_pred_df(closes))
    assert direction == "up"
    assert regime == "trending_up"  # slope ~29% >> 0.002 threshold
    assert 0.0 <= conf <= 1.0


def test_derive_downtrend():
    model = KronosModel.__new__(KronosModel)
    closes = [100.0 - i * 0.5 for i in range(60)]
    regime, direction, short_dir, conf = model._derive_signals(100.0, _make_pred_df(closes))
    assert direction == "down"


def test_derive_volatile():
    model = KronosModel.__new__(KronosModel)
    import random; random.seed(1)
    closes = [100.0 + random.uniform(-5, 5) for _ in range(60)]
    regime, direction, short_dir, conf = model._derive_signals(100.0, _make_pred_df(closes))
    assert regime == "volatile"


def test_derive_ranging():
    model = KronosModel.__new__(KronosModel)
    # Flat line — no slope, low volatility
    closes = [100.0] * 60
    regime, direction, short_dir, conf = model._derive_signals(100.0, _make_pred_df(closes))
    assert regime == "ranging"
    assert direction in ["up", "down"]


def test_derive_short_direction_uses_first_15_bars():
    model = KronosModel.__new__(KronosModel)
    # First 15 bars go up, then reverse sharply
    closes = [101.0 + i for i in range(15)] + [80.0] * 45  # up short, then crash
    regime, direction, short_dir, conf = model._derive_signals(100.0, _make_pred_df(closes))
    assert short_dir == "up"   # first 15 bars are up
    assert direction == "down"  # final close (80.0) < 100.0


def test_predict_returns_neutral_on_empty_klines():
    model = KronosModel(pred_len=60, max_context=512)
    regime, direction, short_dir, conf = model.predict([])
    assert regime == "ranging"
    assert conf == 0.0


def test_predict_calls_predictor_with_correct_columns():
    """predict() should call KronosPredictor.predict with df containing 'amount' column."""
    model = KronosModel(pred_len=5, max_context=512)
    mock_predictor = MagicMock()
    mock_predictor.predict = MagicMock(return_value=_make_pred_df([65100.0] * 5))
    model._predictor = mock_predictor  # inject mock, bypass lazy load

    klines = _fake_klines(50)
    model.predict(klines)

    call_kwargs = mock_predictor.predict.call_args
    df_arg = call_kwargs[1]["df"] if call_kwargs[1] else call_kwargs[0][0]
    assert "amount" in df_arg.columns
    assert "close" in df_arg.columns


def test_predict_returns_valid_literals():
    model = KronosModel(pred_len=5, max_context=512)
    mock_predictor = MagicMock()
    mock_predictor.predict = MagicMock(return_value=_make_pred_df([66000.0] * 5))
    model._predictor = mock_predictor

    klines = _fake_klines(50)
    regime, direction, short_dir, conf = model.predict(klines)
    assert regime in ["trending_up", "trending_down", "ranging", "volatile"]
    assert direction in ["up", "down"]
    assert short_dir in ["up", "down"]
    assert 0.0 <= conf <= 1.0
