"""Tests for MLAgent — the 5th signal provider (Kronos-powered)."""
import numpy as np
import pytest
from unittest.mock import AsyncMock, MagicMock

from cryptoswarm.agents.ml_agent import MLAgent
from cryptoswarm.bus.messages import AnalyzeRequest, MLSignal
from cryptoswarm.ml.features import FEATURE_SIZE


def _make_agent(trained: bool = True):
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_features = MagicMock()
    mock_features.build = AsyncMock(
        return_value=np.zeros(FEATURE_SIZE, dtype=np.float32)
    )
    mock_features._ts = MagicMock()
    mock_features._ts.fetch_klines = AsyncMock(return_value=[
        {"open": 65000.0, "high": 65100.0, "low": 64900.0, "close": 65050.0, "volume": 100.0}
        for _ in range(50)
    ])
    mock_kronos = MagicMock()
    mock_kronos.predict = MagicMock(
        return_value=("trending_up", "up", "up", 0.78) if trained else ("ranging", "up", "up", 0.0)
    )
    mock_ppo = MagicMock()
    mock_ppo.predict = MagicMock(
        return_value=("scale_up", 0.6) if trained else ("hold", 0.0)
    )
    mock_pg = MagicMock()
    mock_pg.insert_ml_signal = AsyncMock()
    return MLAgent(
        bus=mock_bus,
        features=mock_features,
        kronos=mock_kronos,
        ppo=mock_ppo,
        pg=mock_pg,
    )


async def test_ml_agent_publishes_ml_signal():
    agent = _make_agent(trained=True)
    req = AnalyzeRequest(symbol="BTCUSDT")
    await agent._handle(req)
    topic, msg = agent._bus.publish.call_args[0]
    assert topic == "agent.result.ml.BTCUSDT"
    assert isinstance(msg, MLSignal)
    assert msg.regime_pred == "trending_up"
    assert msg.direction_pred == "up"
    assert msg.size_adjustment == "scale_up"


async def test_ml_agent_zero_confidence_when_kronos_returns_zero():
    agent = _make_agent(trained=False)
    req = AnalyzeRequest(symbol="SOLUSDT")
    await agent._handle(req)
    _, msg = agent._bus.publish.call_args[0]
    assert msg.confidence == 0.0
    assert msg.size_adjustment == "hold"


async def test_ml_agent_stores_signal_to_db():
    agent = _make_agent(trained=True)
    req = AnalyzeRequest(symbol="BTCUSDT")
    await agent._handle(req)
    agent._pg.insert_ml_signal.assert_called_once()


async def test_ml_agent_handles_fetch_error_gracefully():
    agent = _make_agent()
    agent._features._ts.fetch_klines = AsyncMock(side_effect=Exception("TS down"))
    req = AnalyzeRequest(symbol="BTCUSDT")
    await agent._handle(req)  # Must not raise
    agent._bus.publish.assert_called_once()


async def test_ml_agent_neutral_fallback_also_stores_to_db():
    """When data fetch fails, _publish_neutral should still write to DB."""
    agent = _make_agent()
    agent._features._ts.fetch_klines = AsyncMock(side_effect=Exception("TS down"))
    req = AnalyzeRequest(symbol="BTCUSDT")
    await agent._handle(req)
    agent._pg.insert_ml_signal.assert_called_once()
    call_kwargs = agent._pg.insert_ml_signal.call_args[1]
    assert call_kwargs["confidence"] == 0.0
    assert call_kwargs["size_adjustment"] == "hold"
