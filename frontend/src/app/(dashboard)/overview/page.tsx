"use client";

import { useEffect, useState, useCallback } from "react";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, CartesianGrid,
} from "recharts";
import { api } from "@/lib/api";
import type { Stats, Position, Trade, AgentStatus, PnlPoint } from "@/lib/types";


// ── helpers ──────────────────────────────────────────────────────────────────

function pnl(v: number | null | undefined, prefix = "") {
  if (v == null) return <span className="text-t3">—</span>;
  const pos = v >= 0;
  return (
    <span className={pos ? "text-gr" : "text-re"}>
      {pos ? "+" : ""}{prefix}{v.toFixed(2)}
    </span>
  );
}

function Badge({ children, color }: { children: React.ReactNode; color: "gr" | "re" | "ye" | "bl" }) {
  const map = {
    gr: "bg-gr/10 text-gr border-gr/20",
    re: "bg-re/10 text-re border-re/20",
    ye: "bg-ye/10 text-ye border-ye/20",
    bl: "bg-bl/10 text-bl border-bl/20",
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-semibold border ${map[color]}`}>
      {children}
    </span>
  );
}

// ── KPI card ─────────────────────────────────────────────────────────────────
interface KpiProps {
  label: string; value: string | React.ReactNode;
  sub?: string; accent?: string; loading?: boolean;
}
function KpiCard({ label, value, sub, accent = "bg-bl", loading }: KpiProps) {
  return (
    <div className="bg-s1 border border-b1 rounded-xl p-5 flex flex-col gap-3 relative overflow-hidden">
      <div className={`absolute top-0 left-0 right-0 h-[2px] ${accent}`} />
      <span className="text-[11px] font-semibold uppercase tracking-widest text-t3">{label}</span>
      {loading
        ? <div className="h-7 w-24 bg-b1 rounded animate-pulse" />
        : <span className="text-2xl font-bold text-t1 leading-none tabular-nums">{value}</span>
      }
      {sub && <span className="text-xs text-t2">{sub}</span>}
    </div>
  );
}

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ title, children, action }: {
  title: string; children: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div className="bg-s1 border border-b1 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-b1">
        <h2 className="text-sm font-semibold text-t1">{title}</h2>
        {action}
      </div>
      {children}
    </div>
  );
}

// ── Custom tooltip for chart ──────────────────────────────────────────────────
function ChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-s2 border border-b1 rounded-lg px-3 py-2 text-xs shadow-xl">
      <p className="text-t2 mb-1">{label}</p>
      <p className="font-semibold text-gr">${payload[0]?.value?.toFixed(2)}</p>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function OverviewPage() {
  const [stats, setStats]         = useState<Stats | null>(null);
  const [positions, setPositions] = useState<{ positions: Position[]; balance: number; equity: number } | null>(null);
  const [trades, setTrades]       = useState<Trade[]>([]);
  const [agents, setAgents]       = useState<AgentStatus[]>([]);
  const [pnlData, setPnlData]     = useState<PnlPoint[]>([]);
  const [loading, setLoading]     = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date>(new Date());

  const load = useCallback(async () => {
    try {
      const [s, pos, t, ag, pnl] = await Promise.all([
        api.stats(),
        api.positions(),
        api.trades(10),
        api.agents(),
        api.pnlHistory(),
      ]);
      setStats(s);
      setPositions(pos);
      setTrades(t);
      setAgents(ag.agents);
      setPnlData(pnl);
      setLastRefresh(new Date());
    } catch (e) {
      console.error("overview load error", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 20_000);
    return () => clearInterval(id);
  }, [load]);

  // Format PnL chart data
  const chartData = pnlData.slice(-40).map((p) => ({
    time: new Date(p.ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    pnl: p.cumulative_pnl,
  }));

  const openPositions = positions?.positions ?? [];
  const closedTrades  = trades.filter((t) => t.closed_ts);
  const unrealizedPnl = openPositions.reduce((sum, p) => sum + p.unrealized_pnl, 0);

  return (
    <div className="space-y-5">

      {/* ── KPI row ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Account Balance"
          value={positions ? `$${positions.balance.toFixed(2)}` : "—"}
          sub={`Equity $${positions?.equity.toFixed(2) ?? "—"}`}
          accent="bg-bl"
          loading={loading}
        />
        <KpiCard
          label="Unrealized P&L"
          value={
            <span className={unrealizedPnl >= 0 ? "text-gr" : "text-re"}>
              {unrealizedPnl >= 0 ? "+" : ""}${unrealizedPnl.toFixed(2)}
            </span>
          }
          sub={`${openPositions.length} open position${openPositions.length !== 1 ? "s" : ""}`}
          accent={unrealizedPnl >= 0 ? "bg-gr" : "bg-re"}
          loading={loading}
        />
        <KpiCard
          label="Win Rate"
          value={stats ? `${(stats.win_rate * 100).toFixed(0)}%` : "—"}
          sub={`${stats?.wins ?? 0}W / ${stats?.losses ?? 0}L`}
          accent="bg-pu"
          loading={loading}
        />
        <KpiCard
          label="Total Trades"
          value={stats?.total_trades ?? "—"}
          sub={`Fees $${stats?.total_fees.toFixed(2) ?? "—"}`}
          accent="bg-ye"
          loading={loading}
        />
      </div>

      {/* ── PnL chart + Agent status ──────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Chart */}
        <Section title="Cumulative P&L" action={
          <span className="text-[11px] text-t3">
            Updated {lastRefresh.toLocaleTimeString()}
          </span>
        }>
          <div className="h-[200px] px-2 pt-4 pb-2">
            {chartData.length > 1 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 0, right: 8, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="#00d084" stopOpacity={0.2} />
                      <stop offset="95%" stopColor="#00d084" stopOpacity={0}   />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1e2d42" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="time" tick={{ fill: "#4a5568", fontSize: 10 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fill: "#4a5568", fontSize: 10 }} tickLine={false} axisLine={false}
                    tickFormatter={(v) => `$${v}`} />
                  <Tooltip content={<ChartTooltip />} />
                  <Area type="monotone" dataKey="pnl" stroke="#00d084" strokeWidth={2}
                    fill="url(#pnlGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex items-center justify-center">
                <p className="text-t3 text-sm">No closed trades yet</p>
              </div>
            )}
          </div>
        </Section>

        {/* Agent status */}
        <Section title="AI Agents">
          <div className="divide-y divide-b1">
            {loading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="flex items-center gap-3 px-5 py-3">
                    <div className="w-2 h-2 rounded-full bg-b1 animate-pulse" />
                    <div className="h-3 w-20 bg-b1 rounded animate-pulse" />
                  </div>
                ))
              : agents.map((a) => (
                  <div key={a.name} className="flex items-center gap-3 px-5 py-3">
                    <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                      a.status === "ok" ? "bg-gr shadow-[0_0_6px_#00d084]"
                        : a.status === "error" ? "bg-re" : "bg-ye"
                    }`} />
                    <span className="text-sm font-medium text-t1 capitalize flex-1">{a.name}</span>
                    <span className="text-[11px] text-t2 truncate max-w-[100px]">{a.last_symbol}</span>
                    <Badge color={a.status === "ok" ? "gr" : a.status === "error" ? "re" : "ye"}>
                      {a.status}
                    </Badge>
                  </div>
                ))
            }
          </div>
        </Section>

        {/* Open positions */}
        <Section title="Open Positions" action={
          <Badge color="bl">{openPositions.length} open</Badge>
        }>
          <div className="divide-y divide-b1">
            {loading
              ? Array.from({ length: 2 }).map((_, i) => (
                  <div key={i} className="px-5 py-3 space-y-1.5">
                    <div className="h-3 w-16 bg-b1 rounded animate-pulse" />
                    <div className="h-3 w-24 bg-b1 rounded animate-pulse" />
                  </div>
                ))
              : openPositions.length === 0
              ? <p className="text-t3 text-sm px-5 py-5 text-center">No open positions</p>
              : openPositions.map((p) => (
                  <div key={p.symbol} className="px-5 py-3.5 flex flex-col gap-1">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold text-t1">{p.symbol}</span>
                        <Badge color={p.side === "LONG" ? "gr" : "re"}>{p.side}</Badge>
                      </div>
                      <span className="text-sm font-semibold">
                        {pnl(p.unrealized_pnl, "$")}
                      </span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-t2">
                      <span>Entry ${p.entry_price.toFixed(2)}</span>
                      <span>Mark ${p.mark_price.toFixed(2)}</span>
                    </div>
                    <div className="text-[11px] text-t3">
                      Liq ${p.liq_price.toFixed(2)} · Qty {p.qty.toFixed(5)}
                    </div>
                  </div>
                ))
            }
          </div>
        </Section>
      </div>

      {/* ── Recent trades ─────────────────────────────────────────── */}
      <Section title="Recent Trades" action={
        <span className="text-[11px] text-t3">{trades.length} total</span>
      }>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[11px] uppercase tracking-wider text-t3 border-b border-b1">
                <th className="text-left px-5 py-2.5 font-medium">Symbol</th>
                <th className="text-left px-3 py-2.5 font-medium">Side</th>
                <th className="text-right px-3 py-2.5 font-medium">Entry</th>
                <th className="text-right px-3 py-2.5 font-medium">Exit</th>
                <th className="text-right px-3 py-2.5 font-medium">P&L</th>
                <th className="text-right px-5 py-2.5 font-medium">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-b1">
              {loading
                ? Array.from({ length: 5 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 6 }).map((_, j) => (
                        <td key={j} className="px-5 py-3">
                          <div className="h-3 bg-b1 rounded animate-pulse w-16" />
                        </td>
                      ))}
                    </tr>
                  ))
                : trades.length === 0
                ? <tr><td colSpan={6} className="text-center text-t3 py-8">No trades yet</td></tr>
                : trades.map((t) => (
                    <tr key={t.id} className="hover:bg-s2 transition-colors">
                      <td className="px-5 py-3 font-semibold text-t1">{t.symbol}</td>
                      <td className="px-3 py-3">
                        <Badge color={t.side === "LONG" ? "gr" : "re"}>{t.side}</Badge>
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums text-t1">
                        ${t.entry_price.toFixed(2)}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums text-t2">
                        {t.exit_price ? `$${t.exit_price.toFixed(2)}` : <span className="text-t3">Open</span>}
                      </td>
                      <td className="px-3 py-3 text-right tabular-nums font-semibold">
                        {pnl(t.realized_pnl, "$")}
                      </td>
                      <td className="px-5 py-3 text-right text-t2 text-[11px] tabular-nums">
                        {new Date(t.opened_ts).toLocaleDateString([], {
                          month: "short", day: "numeric",
                          hour: "2-digit", minute: "2-digit",
                        })}
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>
      </Section>

    </div>
  );
}
