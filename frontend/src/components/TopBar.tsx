"use client";
import { useEffect, useState } from "react";
interface Ticker { price: string; change: string; up: boolean }
async function fetchTicker(symbol: string): Promise<Ticker> {
  const r = await fetch(`https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=${symbol}`);
  const d = await r.json();
  const c = parseFloat(d.priceChangePercent);
  return {
    price: `$${parseFloat(d.lastPrice).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`,
    change: `${c >= 0 ? "+" : ""}${c.toFixed(2)}%`, up: c >= 0
  };
}
export default function TopBar() {
  const [btc, setBtc] = useState<Ticker | null>(null);
  const [eth, setEth] = useState<Ticker | null>(null);
  const [time, setTime] = useState("");
  useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(id);
  }, []);
  useEffect(() => {
    async function load() {
      const [b, e] = await Promise.all([fetchTicker("BTCUSDT"), fetchTicker("ETHUSDT")]);
      setBtc(b); setEth(e);
    }
    load(); const id = setInterval(load, 15000); return () => clearInterval(id);
  }, []);
  return (
    <div className="bg-s1 border-b border-b1 h-14 flex items-center px-6 gap-6 sticky top-0 z-10">
      <div className="flex gap-6 flex-1">
        {btc && <div className="flex items-center gap-2">
          <span className="font-bold text-sm text-ye">BTC</span>
          <span className="text-sm font-semibold tabular-nums">{btc.price}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${btc.up ? "bg-gr/15 text-gr" : "bg-re/15 text-re"}`}>{btc.change}</span>
        </div>}
        {eth && <div className="flex items-center gap-2">
          <span className="font-bold text-sm text-pu">ETH</span>
          <span className="text-sm font-semibold tabular-nums">{eth.price}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded ${eth.up ? "bg-gr/15 text-gr" : "bg-re/15 text-re"}`}>{eth.change}</span>
        </div>}
      </div>
      <span className="text-xs text-t2 tabular-nums">{time}</span>
    </div>
  );
}
