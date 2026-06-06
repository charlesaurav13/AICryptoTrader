"""gRPC server — exposes live positions, agent status, and event stream to Go."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

import grpc
from cryptoswarm.proto import cryptoswarm_pb2 as pb2
from cryptoswarm.proto import cryptoswarm_pb2_grpc as pb2_grpc

if TYPE_CHECKING:
    from cryptoswarm.papertrade.engine import PaperTradeEngine
    from cryptoswarm.bus.client import BusClient

logger = logging.getLogger(__name__)

_AGENT_NAMES = ["quant", "risk", "sentiment", "portfolio", "ml"]


class TradingServicer(pb2_grpc.TradingServiceServicer):
    def __init__(self, engine: "PaperTradeEngine", bus: "BusClient") -> None:
        self._engine = engine
        self._bus = bus
        self._agent_last: dict[str, dict] = {}

    async def GetLivePositions(self, request, context):
        acc = self._engine._account
        positions = [
            pb2.Position(
                symbol=p.symbol,
                side=p.side,
                qty=float(p.qty),
                entry_price=float(p.entry_price),
                mark_price=float(p.mark_price),
                unrealized_pnl=float(p.unrealized_pnl),
                liq_price=float(p.liq_price),
            )
            for p in acc.open_positions.values()
        ]
        return pb2.PositionsResponse(
            positions=positions,
            balance=float(acc.balance),
            equity=float(acc.equity),
        )

    async def GetAgentStatus(self, request, context):
        agents = []
        for name in _AGENT_NAMES:
            info = self._agent_last.get(name, {})
            agents.append(pb2.AgentStatus(
                name=name,
                last_symbol=info.get("symbol", ""),
                last_output=info.get("output", ""),
                status=info.get("status", "idle"),
                last_ts=int(info.get("ts", 0)),
            ))
        return pb2.AgentStatusResponse(agents=agents)

    async def StreamEvents(self, request, context):
        async for topic, data in self._bus.psubscribe("*"):
            if context.cancelled():
                break
            yield pb2.TradeEvent(topic=topic, payload=data)

    def update_agent(self, name: str, symbol: str, output: str) -> None:
        import time
        self._agent_last[name] = {
            "symbol": symbol, "output": output,
            "status": "ok", "ts": int(time.time() * 1000),
        }


async def serve_grpc(engine: "PaperTradeEngine", bus: "BusClient", port: int = 50051) -> None:
    """Run the gRPC server. Call as an asyncio task."""
    servicer = TradingServicer(engine, bus)
    server = grpc.aio.server()
    pb2_grpc.add_TradingServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f"[::]:{port}")
    await server.start()
    logger.info("gRPC server listening on :%d", port)
    await server.wait_for_termination()
