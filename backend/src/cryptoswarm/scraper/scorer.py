"""OpenRouterScorer — scores news relevance + sentiment via OpenRouter."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)

_PROMPT = """You are a crypto trading news scorer.
Given a news article, score its relevance and sentiment for each symbol: {symbols}.

Article title: {title}
Article body: {body}

Return ONLY valid JSON (no markdown, no extra text):
{{
  "SYMBOL1": {{"relevance": 0.0, "sentiment": 0.0, "summary": "max 30 words"}},
  "SYMBOL2": {{"relevance": 0.0, "sentiment": 0.0, "summary": "max 30 words"}}
}}

relevance: 0.0 (unrelated) → 1.0 (directly about this asset)
sentiment: -1.0 (very bearish) → 1.0 (very bullish)"""


@dataclass
class ScoredArticle:
    symbol: str
    relevance: float    # 0.0–1.0
    sentiment: float    # -1.0 to 1.0
    summary: str


class OpenRouterScorer:
    def __init__(self, api_key: str, model: str, symbols: list[str]) -> None:
        self._api_key = api_key
        self._model = model
        self._symbols = list(symbols)

    async def score(self, title: str, body: str) -> list[ScoredArticle]:
        try:
            raw = await self._call(title, body[:500])
            return [
                ScoredArticle(
                    symbol=sym,
                    relevance=max(0.0, min(1.0, float(raw.get(sym, {}).get("relevance", 0.0)))),
                    sentiment=max(-1.0, min(1.0, float(raw.get(sym, {}).get("sentiment", 0.0)))),
                    summary=str(raw.get(sym, {}).get("summary", "")),
                )
                for sym in self._symbols
            ]
        except Exception as exc:
            logger.warning("OpenRouterScorer error: %s — returning neutral scores", exc)
            return [ScoredArticle(symbol=s, relevance=0.0, sentiment=0.0, summary="") for s in self._symbols]

    async def _call(self, title: str, body: str) -> dict:
        prompt = _PROMPT.format(
            symbols=", ".join(self._symbols),
            title=title,
            body=body,
        )
        async with httpx.AsyncClient(timeout=30.0) as client:
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
                    "temperature": 0.1,
                },
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"].strip()
            if "```" in text:
                text = text.split("```")[1].removeprefix("json").strip()
            return json.loads(text)


# Backwards-compatible alias used by existing imports
OllamaScorer = OpenRouterScorer
