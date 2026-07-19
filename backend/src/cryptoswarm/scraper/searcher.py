"""OpenRouter news searcher — uses Perplexity Sonar for real-time web search."""
from __future__ import annotations

import json
import logging
import re

import httpx

logger = logging.getLogger(__name__)

_SEARCH_PROMPT = """Search for the 5 most recent and important crypto news headlines about {symbol} in the last 24 hours.

Return ONLY a JSON array (no markdown, no extra text):
[
  {{"title": "headline here", "body": "2-3 sentence summary of the news", "url": "source url if known else empty string"}},
  ...
]

Focus on: price-moving events, regulatory news, exchange news, major partnerships, hacks, ETF flows, on-chain data."""


class OpenRouterNewsSearcher:
    """Fetches real-time crypto news using Perplexity Sonar via OpenRouter."""

    def __init__(self, api_key: str, model: str, symbols: list[str]) -> None:
        self._api_key = api_key
        self._model = model
        self._symbols = symbols

    async def search_symbol(self, symbol: str) -> list[dict]:
        """Return up to 5 recent news items for a symbol."""
        base = symbol.replace("USDT", "").replace("BUSD", "")
        prompt = _SEARCH_PROMPT.format(symbol=f"{base} ({symbol})")
        try:
            return await self._call(prompt)
        except Exception as exc:
            logger.warning("OpenRouterNewsSearcher: %s error — %s", symbol, exc)
            return []

    async def _call(self, prompt: str) -> list[dict]:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/charlesaurav13/AICryptoTrader",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()

            # Strip markdown fences if present
            text = re.sub(r"```(?:json)?", "", text).strip().rstrip("```").strip()

            # Find the JSON array
            start = text.find("[")
            end = text.rfind("]") + 1
            if start == -1 or end == 0:
                logger.warning("OpenRouterNewsSearcher: no JSON array in response: %s", text[:200])
                return []

            articles = json.loads(text[start:end])
            return [
                {
                    "title": str(a.get("title", "")),
                    "body": str(a.get("body", "")),
                    "url": str(a.get("url", f"openrouter-search-{self._model}")),
                }
                for a in articles
                if isinstance(a, dict) and a.get("title")
            ]
