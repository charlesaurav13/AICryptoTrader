"""Tests for DirectorAgent with 5 signals + prompt reloading."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from cryptoswarm.agents.director import DirectorAgent
from cryptoswarm.bus.messages import (
    AnalyzeRequest, QuantResult, RiskResult,
    SentimentResult, PortfolioResult, MLSignal,
)
from cryptoswarm.config.settings import Settings


def _make_settings():
    return Settings(
        paper_trading=True,
        director_interval_s=9999,
        agent_timeout_s=2,
        symbols="BTCUSDT",
    )


def _make_results(symbol: str, cid: str) -> dict:
    return {
        "quant": QuantResult(
            symbol=symbol, correlation_id=cid,
            regime="trending_up", signal_strength=0.8,
            confidence=0.85, reasoning="EMA cross bullish",
            indicators={"rsi": 65.0, "close": 68000.0},
        ),
        "risk": RiskResult(
            symbol=symbol, correlation_id=cid,
            kelly_fraction=0.06, max_loss_usdt=60.0,
            reasoning="moderate volatility",
        ),
        "sentiment": SentimentResult(
            symbol=symbol, correlation_id=cid,
            score=0.3, source="combined",
            summary="FNG: Greed | News: 3 articles +0.35",
        ),
        "portfolio": PortfolioResult(
            symbol=symbol, correlation_id=cid,
            approved=True, correlation_penalty=1.0,
            reasoning="no correlated positions",
        ),
        "ml": MLSignal(
            symbol=symbol, correlation_id=cid,
            regime_pred="trending_up", direction_pred="up",
            short_direction="up", size_adjustment="scale_up",
            confidence=0.78, reasoning="Kronos-base bullish",
        ),
    }


async def test_director_accepts_5_signals():
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_llm = MagicMock()
    mock_llm.ask = AsyncMock(return_value={
        "action": "buy", "side": "LONG", "confidence": 0.85,
        "size_pct": 0.06, "sl_pct": 0.02, "tp_pct": 0.05,
        "reasoning": "All 5 agents agree bullish",
    })
    mock_decisions = MagicMock()
    mock_decisions.insert = AsyncMock()
    mock_store = MagicMock()
    mock_store.get = AsyncMock(return_value="evolved director prompt")

    agent = DirectorAgent(
        bus=mock_bus, llm=mock_llm,
        decisions=mock_decisions, settings=_make_settings(),
        prompt_store=mock_store,
    )
    req = AnalyzeRequest(symbol="BTCUSDT")
    results = _make_results("BTCUSDT", req.correlation_id)
    await agent._analyze_symbol_with_results("BTCUSDT", req, results)

    published = [c[0][0] for c in mock_bus.publish.call_args_list]
    assert "signal.execute" in published


async def test_director_prompt_included_in_llm_call():
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_llm = MagicMock()
    mock_llm.ask = AsyncMock(return_value={
        "action": "hold", "side": "LONG", "confidence": 0.4,
        "size_pct": 0.0, "sl_pct": 0.02, "tp_pct": 0.04,
        "reasoning": "low confidence",
    })
    mock_decisions = MagicMock()
    mock_decisions.insert = AsyncMock()
    mock_store = MagicMock()
    evolved = "You are an evolved trading chief with improved risk awareness."
    mock_store.get = AsyncMock(return_value=evolved)

    agent = DirectorAgent(
        bus=mock_bus, llm=mock_llm,
        decisions=mock_decisions, settings=_make_settings(),
        prompt_store=mock_store,
    )
    # Force prompt reload by setting cycle_count to trigger reload
    agent._cycle_count = 0
    req = AnalyzeRequest(symbol="BTCUSDT")
    results = _make_results("BTCUSDT", req.correlation_id)
    await agent._analyze_symbol_with_results("BTCUSDT", req, results)

    llm_call_kwargs = mock_llm.ask.call_args
    system_arg = llm_call_kwargs[1].get("system") or llm_call_kwargs[0][0]
    assert system_arg == evolved


async def test_director_ml_summary_in_prompt():
    mock_bus = MagicMock()
    mock_bus.publish = AsyncMock()
    mock_llm = MagicMock()
    mock_llm.ask = AsyncMock(return_value={
        "action": "buy", "side": "LONG", "confidence": 0.82,
        "size_pct": 0.05, "sl_pct": 0.02, "tp_pct": 0.04,
        "reasoning": "Strong signal",
    })
    mock_decisions = MagicMock()
    mock_decisions.insert = AsyncMock()
    mock_store = MagicMock()
    mock_store.get = AsyncMock(return_value="default prompt")

    agent = DirectorAgent(
        bus=mock_bus, llm=mock_llm,
        decisions=mock_decisions, settings=_make_settings(),
        prompt_store=mock_store,
    )
    req = AnalyzeRequest(symbol="BTCUSDT")
    results = _make_results("BTCUSDT", req.correlation_id)
    await agent._analyze_symbol_with_results("BTCUSDT", req, results)

    llm_call = mock_llm.ask.call_args
    prompt_arg = llm_call[1].get("prompt") or llm_call[0][1]
    assert "ML AGENT" in prompt_arg or "Kronos" in prompt_arg or "ml" in prompt_arg.lower()
