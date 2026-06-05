#!/usr/bin/env python3
"""
Backtest 5: SL/TP Optimization Grid
Finds optimal Stop-Loss %, Take-Profit %, and leverage via grid search.

Usage: python backend/scripts/backtest_5_sltp.py
"""
import matplotlib
matplotlib.use("Agg")

import csv
import sys
import time
from datetime import datetime, timedelta, timezone
from math import sqrt
from pathlib import Path

import httpx
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ── Settings ────────────────────────────────────────────────────────────────
SYMBOL    = "BTCUSDT"
DAYS      = 90
INTERVAL  = "1h"
SL_RANGE  = [0.005, 0.01, 0.015, 0.02, 0.03, 0.05]
TP_RANGE  = [0.01, 0.02, 0.03, 0.04, 0.06, 0.08, 0.10]
LEVERAGES = [1, 3, 5, 10, 20]

BASE_URL  = "https://fapi.binance.com"
RESULTS_DIR = Path(__file__).parent.parent / "backtest_results"

# ── Dark theme ───────────────────────────────────────────────────────────────
BG_DARK  = "#0d1117"
BG_AXES  = "#161b22"
FG_TEXT  = "#e6edf3"
FG_DIM   = "#8b949e"

plt.rcParams.update({
    "figure.facecolor":  BG_DARK,
    "axes.facecolor":    BG_AXES,
    "axes.edgecolor":    FG_DIM,
    "axes.labelcolor":   FG_TEXT,
    "xtick.color":       FG_DIM,
    "ytick.color":       FG_DIM,
    "text.color":        FG_TEXT,
    "grid.color":        "#30363d",
    "grid.linestyle":    "--",
    "grid.alpha":        0.5,
    "legend.facecolor":  BG_AXES,
    "legend.edgecolor":  FG_DIM,
})


# ── Data fetch ───────────────────────────────────────────────────────────────
def fetch_klines(symbol: str, interval: str, days: int) -> pd.DataFrame:
    """Fetch historical klines from Binance Futures API (paginated)."""
    target_bars = days * 24  # 1h bars
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = end_ms - days * 24 * 3600 * 1000

    all_rows: list[list] = []
    limit = 1000
    current_start = start_ms

    print(f"  Fetching {target_bars} bars from Binance ({interval}) …", flush=True)
    with httpx.Client(timeout=30) as client:
        while current_start < end_ms:
            resp = client.get(
                f"{BASE_URL}/fapi/v1/klines",
                params={
                    "symbol":    symbol,
                    "interval":  interval,
                    "startTime": current_start,
                    "endTime":   end_ms,
                    "limit":     limit,
                },
            )
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                break
            all_rows.extend(rows)
            last_ts = rows[-1][0]
            if len(rows) < limit:
                break
            current_start = last_ts + 1  # advance past last bar

    df = pd.DataFrame(all_rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_base", "taker_quote", "ignore",
    ])
    df = df.drop_duplicates("open_time").sort_values("open_time").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    print(f"  Got {len(df)} bars  ({df['ts'].iloc[0].date()} → {df['ts'].iloc[-1].date()})")
    return df


# ── Indicators ────────────────────────────────────────────────────────────────
def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def add_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema20"] = ema(df["close"], 20)
    df["rsi14"] = rsi(df["close"], 14)
    df["rsi_prev"] = df["rsi14"].shift(1)

    # Long: close > EMA20, RSI 45-65, RSI rising
    df["long"] = (
        (df["close"] > df["ema20"]) &
        (df["rsi14"] >= 45) & (df["rsi14"] <= 65) &
        (df["rsi14"] > df["rsi_prev"])
    )
    # Short: close < EMA20, RSI 35-55, RSI falling
    df["short"] = (
        (df["close"] < df["ema20"]) &
        (df["rsi14"] >= 35) & (df["rsi14"] <= 55) &
        (df["rsi14"] < df["rsi_prev"])
    )
    return df


# ── Backtest engine ───────────────────────────────────────────────────────────
def run_backtest(df: pd.DataFrame, sl: float, tp: float) -> dict:
    """
    Simulate all entry signals; for each trade scan forward for SL/TP hit.
    Returns per-trade PnL list (as fraction of position, unleveraged).
    """
    closes = df["close"].to_numpy()
    highs  = df["high"].to_numpy()
    lows   = df["low"].to_numpy()
    longs  = df["long"].to_numpy()
    shorts = df["short"].to_numpy()
    n = len(df)

    pnls: list[float] = []

    for i in range(n - 1):
        direction = None
        if longs[i]:
            direction = "long"
        elif shorts[i]:
            direction = "short"
        else:
            continue

        entry = closes[i]
        if direction == "long":
            sl_price = entry * (1 - sl)
            tp_price = entry * (1 + tp)
        else:
            sl_price = entry * (1 + sl)
            tp_price = entry * (1 - tp)

        result_pnl = None
        for j in range(i + 1, n):
            h, l = highs[j], lows[j]
            if direction == "long":
                if l <= sl_price:
                    result_pnl = -sl
                    break
                if h >= tp_price:
                    result_pnl = tp
                    break
            else:
                if h >= sl_price:
                    result_pnl = -sl
                    break
                if l <= tp_price:
                    result_pnl = tp
                    break

        if result_pnl is None:
            # still open at end of data — close at last price
            last = closes[-1]
            result_pnl = (last - entry) / entry if direction == "long" else (entry - last) / entry

        pnls.append(result_pnl)

    return {"pnls": pnls}


def compute_metrics(pnls: list[float], leverage: float = 1.0) -> dict:
    if not pnls:
        return {"win_rate": 0, "avg_pnl": 0, "sharpe": 0, "max_dd": 0, "n_trades": 0}

    # Apply leverage; check liquidation
    lev_pnls = []
    for p in pnls:
        lp = p * leverage
        if lp <= -1.0:
            lp = -1.0  # liquidated
        lev_pnls.append(lp)

    n = len(lev_pnls)
    wins = sum(1 for p in lev_pnls if p > 0)
    win_rate = wins / n
    avg_pnl = sum(lev_pnls) / n

    # Equity curve
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    for p in lev_pnls:
        equity *= (1 + p)
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak
        if dd > max_dd:
            max_dd = dd

    # Sharpe: annualise from per-trade returns
    arr = np.array(lev_pnls, dtype=float)
    std = float(arr.std())
    if std == 0:
        sharpe = 0.0
    else:
        # assume ~6 trades/day on average for annualisation (rough)
        trades_per_day = n / DAYS
        sharpe = float((arr.mean() / std) * sqrt(trades_per_day * 252))

    return {
        "win_rate": win_rate,
        "avg_pnl":  avg_pnl,
        "sharpe":   sharpe,
        "max_dd":   -max_dd,
        "n_trades": n,
    }


# ── Charts ────────────────────────────────────────────────────────────────────
def plot_results(
    results_df: pd.DataFrame,
    lev_metrics: list[dict],
    opt_sl: float,
    opt_tp: float,
    timestamp: str,
) -> Path:
    sl_vals = sorted(results_df["sl"].unique())
    tp_vals = sorted(results_df["tp"].unique())

    # Build Sharpe grid (no leverage)
    grid = np.zeros((len(sl_vals), len(tp_vals)))
    for i, sl in enumerate(sl_vals):
        for j, tp in enumerate(tp_vals):
            row = results_df[(results_df["sl"] == sl) & (results_df["tp"] == tp) & (results_df["leverage"] == 1)]
            if not row.empty:
                grid[i, j] = row.iloc[0]["sharpe"]

    fig, axes = plt.subplots(1, 3, figsize=(20, 6))
    fig.patch.set_facecolor(BG_DARK)

    # ── 1. Heatmap ──
    ax = axes[0]
    ax.set_facecolor(BG_AXES)
    im = ax.imshow(grid, aspect="auto", cmap="RdYlGn", vmin=-1, vmax=3)
    ax.set_xticks(range(len(tp_vals)))
    ax.set_xticklabels([f"{v*100:.0f}%" for v in tp_vals], fontsize=8)
    ax.set_yticks(range(len(sl_vals)))
    ax.set_yticklabels([f"{v*100:.1f}%" for v in sl_vals], fontsize=8)
    ax.set_xlabel("Take-Profit %")
    ax.set_ylabel("Stop-Loss %")
    ax.set_title("Sharpe Ratio Grid (1x leverage)", color=FG_TEXT, pad=10)
    cb = fig.colorbar(im, ax=ax)
    cb.ax.yaxis.set_tick_params(color=FG_DIM)
    cb.outline.set_edgecolor(FG_DIM)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color=FG_DIM)
    # Mark optimal
    opt_sl_idx = sl_vals.index(opt_sl) if opt_sl in sl_vals else 0
    opt_tp_idx = tp_vals.index(opt_tp) if opt_tp in tp_vals else 0
    ax.plot(opt_tp_idx, opt_sl_idx, "w*", markersize=12, label="Optimal")
    ax.legend(loc="upper right", fontsize=8)

    # ── 2. MaxDrawdown by leverage ──
    ax = axes[1]
    ax.set_facecolor(BG_AXES)
    lev_labels = [str(m["leverage"]) + "x" for m in lev_metrics]
    lev_dds    = [m["max_dd"] * 100 for m in lev_metrics]
    colors = ["#3fb950" if d > -30 else "#d29922" if d > -60 else "#f85149" for d in lev_dds]
    bars = ax.bar(lev_labels, lev_dds, color=colors, width=0.5)
    for bar, val in zip(bars, lev_dds):
        ax.text(bar.get_x() + bar.get_width() / 2, val - 2, f"{val:.1f}%",
                ha="center", va="top", fontsize=9, color=FG_TEXT)
    ax.set_xlabel("Leverage")
    ax.set_ylabel("Max Drawdown (%)")
    ax.set_title(f"Max Drawdown by Leverage\n(SL={opt_sl*100:.1f}%, TP={opt_tp*100:.1f}%)", color=FG_TEXT, pad=10)
    ax.axhline(-30, color="#d29922", linestyle="--", alpha=0.5, linewidth=1, label="-30% caution")
    ax.axhline(-60, color="#f85149", linestyle="--", alpha=0.5, linewidth=1, label="-60% danger")
    ax.legend(fontsize=8)
    ax.grid(axis="y")

    # ── 3. Win rate vs R:R ratio ──
    ax = axes[2]
    ax.set_facecolor(BG_AXES)
    # Compute for 1x leverage, average over all SL values grouped by R:R
    rr_dict: dict[float, list[float]] = {}
    for _, row in results_df[results_df["leverage"] == 1].iterrows():
        rr = round(row["tp"] / row["sl"], 2)
        rr_dict.setdefault(rr, []).append(row["win_rate"] * 100)
    rr_sorted = sorted(rr_dict.keys())
    wr_avg = [np.mean(rr_dict[r]) for r in rr_sorted]
    ax.plot(rr_sorted, wr_avg, color="#58a6ff", marker="o", linewidth=2, markersize=5)
    ax.axhline(50, color=FG_DIM, linestyle="--", alpha=0.5, linewidth=1, label="50% break-even")
    ax.set_xlabel("R:R Ratio (TP / SL)")
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Win Rate vs R:R Ratio", color=FG_TEXT, pad=10)
    ax.legend(fontsize=8)
    ax.grid()

    fig.suptitle(
        f"Backtest 5 — SL/TP Optimization | {SYMBOL} | {DAYS}d {INTERVAL}",
        color=FG_TEXT, fontsize=13, y=1.01,
    )
    plt.tight_layout()

    out_path = RESULTS_DIR / f"backtest_5_sltp_{timestamp}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG_DARK)
    plt.close(fig)
    return out_path


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 52)
    print("  Backtest 5: SL/TP Optimization")
    print(f"  {SYMBOL} | {DAYS}d {INTERVAL} bars | EMA+RSI signals")
    print("=" * 52)

    df = fetch_klines(SYMBOL, INTERVAL, DAYS)
    df = add_signals(df)

    n_long  = df["long"].sum()
    n_short = df["short"].sum()
    print(f"  Signals: {n_long} long, {n_short} short  ({n_long + n_short} total)")

    # ── Grid search ──
    total = len(SL_RANGE) * len(TP_RANGE)
    print(f"\n  Running {total} SL/TP combinations × {len(LEVERAGES)} leverages …")

    rows: list[dict] = []
    done = 0
    for sl in SL_RANGE:
        for tp in TP_RANGE:
            bt = run_backtest(df, sl, tp)
            for lev in LEVERAGES:
                m = compute_metrics(bt["pnls"], leverage=lev)
                rows.append({
                    "sl":        sl,
                    "tp":        tp,
                    "leverage":  lev,
                    "win_rate":  m["win_rate"],
                    "avg_pnl":   m["avg_pnl"],
                    "sharpe":    m["sharpe"],
                    "max_dd":    m["max_dd"],
                    "n_trades":  m["n_trades"],
                })
            done += 1
            if done % 10 == 0:
                print(f"    {done}/{total} combinations done …", flush=True)

    results_df = pd.DataFrame(rows)

    # ── CSV ──
    csv_path = RESULTS_DIR / "sltp_grid.csv"
    results_df.to_csv(csv_path, index=False)
    print(f"\n  Grid saved → {csv_path}")

    # ── Top combinations (1x leverage, ranked by Sharpe) ──
    lev1 = results_df[results_df["leverage"] == 1].copy()
    top5 = lev1.nlargest(5, "sharpe").reset_index(drop=True)

    opt_row = top5.iloc[0]
    opt_sl  = opt_row["sl"]
    opt_tp  = opt_row["tp"]
    rr      = opt_tp / opt_sl

    print()
    print("=" * 56)
    print("  Top 5 combinations (by Sharpe, 1x leverage):")
    print()
    print(f"  {'Rank':<5} {'SL%':<8} {'TP%':<8} {'Win%':<8} {'AvgPnL':<10} {'Sharpe':<9} {'MaxDD'}")
    for rank, (_, r) in enumerate(top5.iterrows(), 1):
        print(
            f"  {rank:<5} {r['sl']*100:<7.1f}% {r['tp']*100:<7.1f}% "
            f"{r['win_rate']*100:<7.1f}% {r['avg_pnl']*100:>+6.2f}%   "
            f"{r['sharpe']:<8.2f}  {r['max_dd']*100:.1f}%"
        )

    print()
    print(f"  Optimal: SL={opt_sl*100:.1f}%, TP={opt_tp*100:.1f}%  (R:R ratio = {rr:.1f})")
    print()

    # ── Leverage comparison at optimal SL/TP ──
    lev_rows = results_df[
        (results_df["sl"] == opt_sl) & (results_df["tp"] == opt_tp)
    ].sort_values("leverage").to_dict("records")

    print("  By Leverage (optimal SL/TP):")
    for m in lev_rows:
        lev   = m["leverage"]
        sharpe = m["sharpe"]
        dd    = m["max_dd"] * 100
        if dd > -20:
            tag = "Safe"
        elif dd > -50:
            tag = "Moderate"
        elif dd > -75:
            tag = "Risky"
        else:
            tag = "Dangerous"
        print(f"  {lev:<3}x  Sharpe={sharpe:.2f}  MaxDD={dd:.1f}%  {tag}")

    print()

    # ── Charts ──
    chart_path = plot_results(results_df, lev_rows, opt_sl, opt_tp, timestamp)
    print(f"  Chart saved → {chart_path}")
    print("=" * 56)
    print("  Backtest 5 complete.")
    print("=" * 56)


if __name__ == "__main__":
    main()
