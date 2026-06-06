export interface Trade {
  id: number; symbol: string; side: "LONG" | "SHORT"; leverage: number;
  qty: number; entry_price: number; exit_price?: number; exit_reason?: string;
  sl: number; tp: number; realized_pnl?: number; fees: number;
  opened_ts: string; closed_ts?: string;
}

export interface Position {
  symbol: string; side: "LONG" | "SHORT"; qty: number;
  entry_price: number; mark_price: number; unrealized_pnl: number; liq_price: number;
}

export interface PositionsResponse {
  positions: Position[]; balance: number; equity: number;
}

export interface Stats {
  total_trades: number; wins: number; losses: number;
  total_pnl: number; total_fees: number; open_count: number; win_rate: number;
}

export interface Decision {
  correlation_id: string; agent_name: string;
  output: Record<string, unknown>; reasoning?: string;
  confidence?: number; ts: string;
}

export interface MLSignal {
  symbol: string; ts: string; regime_pred: string; direction_pred: string;
  short_direction: string; confidence: number; size_adjustment: string; model_version: string;
}

export interface PnlPoint {
  ts: string; realized_pnl: number; cumulative_pnl: number;
}

export interface AgentStatus {
  name: string; last_symbol: string; last_output: string;
  status: "ok" | "idle" | "error"; last_ts: number;
}

export interface WsEvent { topic: string; payload: unknown; }
