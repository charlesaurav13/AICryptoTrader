"""
Kronos Backtester
=================
Downloads 90 days of 1m klines from Binance public API,
runs Kronos-base on sliding windows, and measures:

  1. Direction accuracy  — did Kronos predict up/down correctly?
  2. Simulated P&L       — trade every signal with SL=2% / TP=4%
  3. Confidence calibration — does higher conf = higher accuracy?
  4. Per-regime breakdown   — how accurate in each market regime?

Usage:
  cd AI_Trading
  source backend/.venv/bin/activate
  python backend/scripts/backtest_kronos.py

Options (edit SETTINGS below):
  SYMBOLS      — list of symbols to backtest
  DAYS         — how many days of history to use
  STEP_HOURS   — how often to sample a prediction window
  SL_PCT       — stop-loss percentage (e.g. 0.02 = 2%)
  TP_PCT       — take-profit percentage (e.g. 0.04 = 4%)
  PRED_LEN     — how many bars Kronos predicts (must match KronosModel)
  SEQ_LEN      — input bars fed to Kronos (context window)
"""

import sys, os, time, json
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ── Settings ──────────────────────────────────────────────────────────────────
SYMBOLS     = ["BTCUSDT", "ETHUSDT"]
DAYS        = 90           # days of history to download
STEP_HOURS  = 4            # prediction every N hours (lower = slower but more samples)
SL_PCT      = 0.02         # stop-loss  2%
TP_PCT      = 0.04         # take-profit 4%
PRED_LEN    = 60           # bars Kronos looks ahead
SEQ_LEN     = 512          # input bars to Kronos
RESULTS_DIR = Path(__file__).parent.parent / "backtest_results"
RESULTS_DIR.mkdir(exist_ok=True)

# ── Add src to path ───────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ── Binance kline downloader ──────────────────────────────────────────────────
BINANCE_BASE = "https://fapi.binance.com"  # futures public endpoint

def fetch_klines_binance(symbol: str, days: int) -> pd.DataFrame:
    """Download 1m klines from Binance futures (no API key needed)."""
    print(f"  Downloading {symbol} ({days}d of 1m klines)...", end="", flush=True)
    end_ms   = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_ms = end_ms - days * 24 * 3600 * 1000
    all_rows = []
    limit    = 1000  # Binance max per request

    with httpx.Client(timeout=30) as client:
        cur = start_ms
        while cur < end_ms:
            resp = client.get(
                f"{BINANCE_BASE}/fapi/v1/klines",
                params={"symbol": symbol, "interval": "1m",
                        "startTime": cur, "endTime": end_ms, "limit": limit},
            )
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                break
            all_rows.extend(rows)
            cur = rows[-1][0] + 60_000  # next bar
            print(".", end="", flush=True)
            time.sleep(0.05)  # be gentle with the API

    df = pd.DataFrame(all_rows, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_vol","trades","taker_buy_base",
        "taker_buy_quote","ignore"
    ])
    df["ts"]     = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open","high","low","close","volume"]:
        df[col] = df[col].astype(float)
    df = df.set_index("ts").sort_index()
    # drop duplicates
    df = df[~df.index.duplicated(keep="last")]
    print(f" {len(df):,} bars")
    return df[["open","high","low","close","volume"]]


# ── Kronos wrapper ─────────────────────────────────────────────────────────────
def load_kronos():
    """Load Kronos model (cached after first call)."""
    print("  Loading Kronos-base (may take a moment on first run)...")
    from cryptoswarm.ml.kronos_model import KronosModel
    model = KronosModel(pred_len=PRED_LEN, max_context=SEQ_LEN, verbose=False)
    model._ensure_loaded()
    print("  Kronos loaded.")
    return model


def run_kronos_window(model, window_df: pd.DataFrame):
    """
    Run Kronos on a window of OHLCV data.
    Returns (regime, direction, short_direction, confidence) or None on error.
    """
    klines = window_df[["open","high","low","close","volume"]].to_dict("records")
    try:
        regime, direction, short_dir, conf = model.predict(klines, interval_minutes=1)
        return regime, direction, short_dir, conf
    except Exception as e:
        return None


# ── Trade simulation ──────────────────────────────────────────────────────────
def simulate_trade(future_bars: pd.DataFrame, side: str, entry: float) -> dict:
    """
    Simulate a trade using future bars after entry.
    side: 'long' or 'short'
    Returns dict with: outcome (tp/sl/timeout), pnl_pct, bars_held
    """
    sl = entry * (1 - SL_PCT) if side == "long" else entry * (1 + SL_PCT)
    tp = entry * (1 + TP_PCT) if side == "long" else entry * (1 - TP_PCT)

    for i, (_, row) in enumerate(future_bars.iterrows()):
        high, low = row["high"], row["low"]
        if side == "long":
            if low  <= sl: return {"outcome":"sl","pnl_pct":-SL_PCT,"bars":i+1}
            if high >= tp: return {"outcome":"tp","pnl_pct":+TP_PCT,"bars":i+1}
        else:
            if high >= sl: return {"outcome":"sl","pnl_pct":-SL_PCT,"bars":i+1}
            if low  <= tp: return {"outcome":"tp","pnl_pct":+TP_PCT,"bars":i+1}

    # timed out — exit at last close
    exit_price = future_bars["close"].iloc[-1] if len(future_bars) > 0 else entry
    pnl = (exit_price - entry) / entry if side == "long" else (entry - exit_price) / entry
    return {"outcome":"timeout","pnl_pct":pnl,"bars":len(future_bars)}


# ── Main backtest loop ────────────────────────────────────────────────────────
def backtest_symbol(symbol: str, df: pd.DataFrame, model) -> pd.DataFrame:
    print(f"\n  Backtesting {symbol}...")
    step_bars = STEP_HOURS * 60  # bars per step
    results   = []
    total_windows = (len(df) - SEQ_LEN - PRED_LEN) // step_bars

    i = SEQ_LEN
    window_num = 0
    while i + PRED_LEN < len(df):
        window_num += 1
        if window_num % 20 == 0:
            pct = window_num / max(total_windows, 1) * 100
            print(f"    [{pct:.0f}%] window {window_num}/{total_windows}", end="\r")

        window   = df.iloc[i - SEQ_LEN : i]
        future   = df.iloc[i : i + PRED_LEN]
        entry_ts = df.index[i]
        entry_px = df["close"].iloc[i]

        result = run_kronos_window(model, window)
        if result is None:
            i += step_bars
            continue

        regime, direction, short_dir, conf = result

        # Actual direction: did price go up or down PRED_LEN bars later?
        future_close  = df["close"].iloc[min(i + PRED_LEN, len(df)-1)]
        actual_dir    = "up" if future_close > entry_px else "down"
        dir_correct   = (direction == actual_dir)

        # Actual short direction (first 15 bars)
        future_15     = df["close"].iloc[min(i + 15, len(df)-1)]
        actual_short  = "up" if future_15 > entry_px else "down"
        short_correct = (short_dir == actual_short)

        # Simulate trade following Kronos direction signal
        side = "long" if direction == "up" else "short"
        trade = simulate_trade(future, side, entry_px)

        results.append({
            "ts":            entry_ts,
            "symbol":        symbol,
            "entry_price":   entry_px,
            "regime":        regime,
            "pred_direction":direction,
            "pred_short":    short_dir,
            "confidence":    conf,
            "actual_direction": actual_dir,
            "actual_short":  actual_short,
            "dir_correct":   dir_correct,
            "short_correct": short_correct,
            "trade_outcome": trade["outcome"],
            "trade_pnl_pct": trade["pnl_pct"],
            "bars_held":     trade["bars"],
        })
        i += step_bars

    print(f"    Done — {len(results)} windows evaluated.     ")
    return pd.DataFrame(results)


# ── Report & charts ───────────────────────────────────────────────────────────
def print_report(df: pd.DataFrame, symbol: str):
    if df.empty:
        print(f"  No results for {symbol}")
        return

    total   = len(df)
    acc     = df["dir_correct"].mean() * 100
    tp_rate = (df["trade_outcome"] == "tp").mean() * 100
    sl_rate = (df["trade_outcome"] == "sl").mean() * 100
    tot_pnl = df["trade_pnl_pct"].sum() * 100
    avg_pnl = df["trade_pnl_pct"].mean() * 100

    print(f"\n{'='*55}")
    print(f"  {symbol} — Kronos Backtest Report")
    print(f"{'='*55}")
    print(f"  Period:       {df['ts'].min().date()} → {df['ts'].max().date()}")
    print(f"  Windows:      {total}")
    print(f"  Step:         {STEP_HOURS}h")
    print(f"  Prediction:   {PRED_LEN} bars ahead")
    print(f"\n  Direction Accuracy:  {acc:.1f}%  (random baseline = 50%)")
    print(f"  TP hit rate:         {tp_rate:.1f}%")
    print(f"  SL hit rate:         {sl_rate:.1f}%")
    print(f"  Avg trade P&L:       {avg_pnl:+.2f}%")
    print(f"  Total sim P&L:       {tot_pnl:+.1f}%  (sum of all trades)")

    print(f"\n  By Regime:")
    for regime, grp in df.groupby("regime"):
        racc = grp["dir_correct"].mean() * 100
        print(f"    {regime:<15} n={len(grp):>4}  acc={racc:.1f}%")

    print(f"\n  Confidence Buckets (accuracy):")
    df["conf_bucket"] = pd.cut(df["confidence"], bins=[0,.5,.6,.7,.8,.9,1.01],
                                labels=["<50%","50-60%","60-70%","70-80%","80-90%","90%+"])
    for bkt, grp in df.groupby("conf_bucket", observed=True):
        bacc = grp["dir_correct"].mean() * 100
        print(f"    conf {bkt:<8}  n={len(grp):>4}  acc={bacc:.1f}%")

    verdict = "✅ EDGE" if acc > 53 else ("⚠️  WEAK" if acc > 50 else "❌ NO EDGE")
    print(f"\n  Verdict: {verdict}")
    print(f"{'='*55}")


def plot_results(dfs: dict, out_path: Path):
    """Generate a 4-panel backtest report chart."""
    fig = plt.figure(figsize=(16, 10), facecolor="#0d1117")
    fig.suptitle("Kronos-base Backtest Report", color="white", fontsize=14, fontweight="bold")
    gs  = gridspec.GridSpec(2, 2, figure=fig, hspace=0.4, wspace=0.3)

    colors = {"BTCUSDT": "#f2a900", "ETHUSDT": "#8c8cff"}

    # ── Panel 1: Cumulative P&L ──────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor("#161b22")
    ax1.set_title("Cumulative Simulated P&L (%)", color="white", fontsize=11)
    for sym, df in dfs.items():
        cum = df["trade_pnl_pct"].cumsum() * 100
        ax1.plot(range(len(cum)), cum, label=sym, color=colors.get(sym, "cyan"), linewidth=1.5)
    ax1.axhline(0, color="#30363d", linewidth=0.8)
    ax1.set_xlabel("Trade #", color="#8b949e", fontsize=9)
    ax1.set_ylabel("Cumulative P&L %", color="#8b949e", fontsize=9)
    ax1.tick_params(colors="#8b949e")
    ax1.spines[:].set_color("#30363d")
    ax1.legend(facecolor="#161b22", labelcolor="white", fontsize=9)

    # ── Panel 2: Direction accuracy (rolling 50-window) ──────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor("#161b22")
    ax2.set_title("Rolling Direction Accuracy (50-window)", color="white", fontsize=11)
    for sym, df in dfs.items():
        roll = df["dir_correct"].rolling(50).mean() * 100
        ax2.plot(range(len(roll)), roll, label=sym, color=colors.get(sym, "cyan"), linewidth=1.5)
    ax2.axhline(50, color="#f85149", linewidth=1, linestyle="--", label="50% baseline")
    ax2.set_ylim(30, 75)
    ax2.set_xlabel("Trade #", color="#8b949e", fontsize=9)
    ax2.set_ylabel("Accuracy %", color="#8b949e", fontsize=9)
    ax2.tick_params(colors="#8b949e")
    ax2.spines[:].set_color("#30363d")
    ax2.legend(facecolor="#161b22", labelcolor="white", fontsize=9)

    # ── Panel 3: Confidence calibration ──────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_facecolor("#161b22")
    ax3.set_title("Confidence Calibration", color="white", fontsize=11)
    all_df = pd.concat(list(dfs.values()))
    buckets = [0, .5, .6, .7, .8, .9, 1.01]
    lbls    = ["<50", "50-60", "60-70", "70-80", "80-90", "90+"]
    all_df["cb"] = pd.cut(all_df["confidence"], bins=buckets, labels=lbls)
    grp = all_df.groupby("cb", observed=True)["dir_correct"].mean() * 100
    bars = ax3.bar(range(len(grp)), grp.values, color="#58a6ff", alpha=0.8, width=0.6)
    ax3.axhline(50, color="#f85149", linewidth=1, linestyle="--")
    ax3.set_xticks(range(len(lbls)))
    ax3.set_xticklabels(lbls, color="#8b949e", fontsize=9)
    ax3.set_ylabel("Accuracy %", color="#8b949e", fontsize=9)
    ax3.set_xlabel("Confidence bucket", color="#8b949e", fontsize=9)
    ax3.tick_params(colors="#8b949e")
    ax3.spines[:].set_color("#30363d")
    ax3.set_ylim(0, 80)
    for bar, val in zip(bars, grp.values):
        ax3.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                 f"{val:.0f}%", ha="center", color="white", fontsize=8)

    # ── Panel 4: Regime breakdown ─────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor("#161b22")
    ax4.set_title("Accuracy by Regime", color="white", fontsize=11)
    rgrp = all_df.groupby("regime")["dir_correct"].agg(["mean","count"])
    rgrp["mean"] *= 100
    regime_colors = {"volatile":"#d29922","trending_up":"#3fb950","trending_down":"#f85149","ranging":"#8b949e"}
    rbars = ax4.bar(range(len(rgrp)), rgrp["mean"].values,
                    color=[regime_colors.get(r, "#58a6ff") for r in rgrp.index],
                    alpha=0.85, width=0.6)
    ax4.axhline(50, color="#f85149", linewidth=1, linestyle="--")
    ax4.set_xticks(range(len(rgrp)))
    ax4.set_xticklabels([f"{r}\n(n={rgrp['count'][r]})" for r in rgrp.index],
                        color="#8b949e", fontsize=8)
    ax4.set_ylabel("Accuracy %", color="#8b949e", fontsize=9)
    ax4.tick_params(colors="#8b949e")
    ax4.spines[:].set_color("#30363d")
    ax4.set_ylim(0, 80)
    for bar, val in zip(rbars, rgrp["mean"].values):
        ax4.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                 f"{val:.0f}%", ha="center", color="white", fontsize=8)

    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    print(f"\n  Chart saved: {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print("\n" + "="*55)
    print("  Kronos-base Backtester")
    print(f"  Symbols: {SYMBOLS}")
    print(f"  Period:  {DAYS} days of 1m klines")
    print(f"  Step:    every {STEP_HOURS}h  |  Pred: {PRED_LEN} bars  |  Seq: {SEQ_LEN} bars")
    print(f"  SL: {SL_PCT*100:.0f}%  TP: {TP_PCT*100:.0f}%")
    print("="*55 + "\n")

    # 1. Load Kronos
    model = load_kronos()

    all_results = {}
    for symbol in SYMBOLS:
        # 2. Download data
        print(f"\n[{symbol}] Step 1/2: Downloading historical data")
        df = fetch_klines_binance(symbol, DAYS)

        # Save raw data
        raw_path = RESULTS_DIR / f"{symbol}_klines_{DAYS}d.parquet"
        df.to_parquet(raw_path)
        print(f"  Saved to {raw_path}")

        # 3. Run backtest
        print(f"[{symbol}] Step 2/2: Running Kronos on {(len(df)-SEQ_LEN-PRED_LEN)//( STEP_HOURS*60):,} windows...")
        t0 = time.time()
        results = backtest_symbol(symbol, df, model)
        elapsed = time.time() - t0
        print(f"  Completed in {elapsed/60:.1f} minutes")

        # Save results
        csv_path = RESULTS_DIR / f"{symbol}_backtest.csv"
        results.to_csv(csv_path, index=False)
        print(f"  Results saved: {csv_path}")

        # Print report
        print_report(results, symbol)
        all_results[symbol] = results

    # 4. Generate charts
    if all_results:
        chart_path = RESULTS_DIR / f"kronos_backtest_{datetime.now().strftime('%Y%m%d_%H%M')}.png"
        print("\nGenerating charts...")
        plot_results(all_results, chart_path)

    print("\nBacktest complete. Results in:", RESULTS_DIR)


if __name__ == "__main__":
    main()
