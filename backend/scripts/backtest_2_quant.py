"""
Backtest 2: Technical Indicator Signals
Tests whether RSI, MACD, EMA cross, Bollinger Bands, ADX predict price direction
better than random chance.
"""

import sys
import time
import datetime
import csv
from pathlib import Path
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

import httpx
import numpy as np
import pandas as pd
import ta

# ── Settings ────────────────────────────────────────────────────────────────
SYMBOLS    = ["BTCUSDT", "ETHUSDT"]
DAYS       = 90
LOOKAHEAD  = 60    # bars ahead to check direction
STEP_HOURS = 1     # sample every 1 hour

RESULTS_DIR = Path(__file__).parent.parent / "backtest_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

BINANCE_BASE = "https://fapi.binance.com/fapi/v1/klines"
INTERVAL     = "1m"

# ── Data fetching ────────────────────────────────────────────────────────────

def fetch_klines(symbol: str, days: int) -> pd.DataFrame:
    """Fetch 1-minute OHLCV data from Binance futures public API."""
    end_ms   = int(time.time() * 1000)
    start_ms = end_ms - days * 24 * 60 * 60 * 1000

    bars = []
    current_start = start_ms

    print(f"  Fetching {symbol} klines ({days}d)...", end="", flush=True)
    with httpx.Client(timeout=30) as client:
        while current_start < end_ms:
            resp = client.get(BINANCE_BASE, params={
                "symbol":    symbol,
                "interval":  INTERVAL,
                "startTime": current_start,
                "limit":     1000,
            })
            resp.raise_for_status()
            chunk = resp.json()
            if not chunk:
                break
            bars.extend(chunk)
            # last bar open time + 1 ms
            current_start = int(chunk[-1][0]) + 1
            if len(chunk) < 1000:
                break
            time.sleep(0.05)
            print(".", end="", flush=True)

    print(f" {len(bars)} bars")

    df = pd.DataFrame(bars, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_base", "taker_quote", "ignore"
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df.set_index("open_time", inplace=True)
    df.sort_index(inplace=True)
    return df


# ── Signal computation ───────────────────────────────────────────────────────

def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Add RSI, MACD, EMA, BB, ADX and derived signal columns."""
    close = df["close"]
    high  = df["high"]
    low   = df["low"]

    # RSI
    rsi_ind = ta.momentum.RSIIndicator(close=close, window=14)
    df["rsi"] = rsi_ind.rsi()

    # MACD
    macd_ind = ta.trend.MACD(close=close)
    df["macd_hist"] = macd_ind.macd_diff()

    # EMA 20/50
    df["ema20"] = ta.trend.EMAIndicator(close=close, window=20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(close=close, window=50).ema_indicator()

    # Bollinger Bands
    bb_ind = ta.volatility.BollingerBands(close=close, window=20, window_dev=2)
    df["bb_upper"] = bb_ind.bollinger_hband()
    df["bb_lower"] = bb_ind.bollinger_lband()

    # ADX
    adx_ind = ta.trend.ADXIndicator(high=high, low=low, close=close, window=14)
    df["adx"] = adx_ind.adx()

    # ── Signal columns: +1 long, -1 short, 0 neutral ──
    # RSI
    df["sig_rsi"] = 0
    df.loc[df["rsi"] < 30, "sig_rsi"] = 1
    df.loc[df["rsi"] > 70, "sig_rsi"] = -1

    # MACD
    df["sig_macd"] = np.where(df["macd_hist"] > 0, 1, -1)

    # EMA cross
    df["sig_ema"] = np.where(df["ema20"] > df["ema50"], 1, -1)

    # Bollinger Band
    df["sig_bb"] = 0
    df.loc[df["close"] < df["bb_lower"], "sig_bb"] = 1
    df.loc[df["close"] > df["bb_upper"], "sig_bb"] = -1

    # ADX trend
    df["sig_adx"] = 0
    ema_cross_long  = df["ema20"] > df["ema50"]
    ema_cross_short = df["ema20"] <= df["ema50"]
    strong_trend    = df["adx"] > 25
    df.loc[strong_trend & ema_cross_long,  "sig_adx"] = 1
    df.loc[strong_trend & ema_cross_short, "sig_adx"] = -1

    # Combined: majority vote of the 5 signals
    sig_cols = ["sig_rsi", "sig_macd", "sig_ema", "sig_bb", "sig_adx"]
    vote_sum = df[sig_cols].sum(axis=1)
    df["sig_combined"] = np.sign(vote_sum).astype(int)
    # If exactly 0, default to long (tie-break)
    df.loc[df["sig_combined"] == 0, "sig_combined"] = 1

    return df


# ── Evaluation ───────────────────────────────────────────────────────────────

SIGNAL_NAMES = {
    "sig_rsi":      "RSI",
    "sig_macd":     "MACD",
    "sig_ema":      "EMA Cross",
    "sig_bb":       "Bollinger Band",
    "sig_adx":      "ADX Trend",
    "sig_combined": "Combined",
}

def evaluate(df: pd.DataFrame, step_hours: int, lookahead: int) -> dict:
    """
    For every STEP_HOURS-th bar, check each signal vs actual direction
    LOOKAHEAD bars later. Returns per-signal stats.
    """
    close = df["close"].values
    n     = len(close)
    step  = step_hours * 60  # 1h = 60 1-minute bars

    results = {col: {"correct": 0, "total": 0, "neutral": 0,
                     "rolling_correct": [], "rolling_total": []}
               for col in SIGNAL_NAMES}
    rows = []

    indices = range(0, n - lookahead, step)
    for i in indices:
        future_price   = close[i + lookahead]
        current_price  = close[i]
        actual_dir     = 1 if future_price > current_price else -1

        row = {"bar_idx": i, "timestamp": df.index[i], "actual_dir": actual_dir}

        for col in SIGNAL_NAMES:
            sig = int(df[col].iloc[i])
            row[col] = sig

            if sig == 0:
                results[col]["neutral"] += 1
                results[col]["rolling_correct"].append(None)
                results[col]["rolling_total"].append(None)
            else:
                correct = int(sig == actual_dir)
                results[col]["correct"] += correct
                results[col]["total"]   += 1
                results[col]["rolling_correct"].append(correct)
                results[col]["rolling_total"].append(1)

        rows.append(row)

    # Compute accuracy
    for col, stats in results.items():
        t = stats["total"]
        stats["accuracy"]  = stats["correct"] / t if t > 0 else 0.0
        stats["neutral_pct"] = stats["neutral"] / len(indices) if indices else 0.0
        stats["signals"]   = t

    return results, pd.DataFrame(rows)


# ── Rolling accuracy for combined signal ─────────────────────────────────────

def rolling_accuracy(df_rows: pd.DataFrame, col: str, window: int = 50) -> pd.Series:
    """Compute rolling accuracy ignoring neutral bars."""
    non_neutral = df_rows[df_rows[col] != 0].copy()
    non_neutral["correct"] = (non_neutral[col] == non_neutral["actual_dir"]).astype(float)
    rolled = non_neutral["correct"].rolling(window, min_periods=window // 2).mean()
    rolled.index = non_neutral["timestamp"]
    return rolled


# ── Verdict helper ────────────────────────────────────────────────────────────

def verdict(combined_acc: float) -> str:
    if combined_acc >= 0.58:
        return "STRONG EDGE (combined >= 58%)"
    elif combined_acc >= 0.55:
        return "WEAK EDGE (combined > 55%)"
    elif combined_acc >= 0.52:
        return "MARGINAL EDGE (combined > 52%)"
    else:
        return "NO EDGE (combined <= 52%)"


# ── Printing ──────────────────────────────────────────────────────────────────

def print_report(symbol: str, results: dict):
    print()
    print("=" * 56)
    print(f"  Backtest 2: Technical Indicator Signals")
    print(f"  {symbol} | {DAYS} days | {STEP_HOURS}h step | {LOOKAHEAD}-bar lookahead")
    print("=" * 56)
    header = f"  {'Signal':<18} {'Accuracy':>10}  {'Signals':>8}  {'Neutral%':>9}"
    print(header)
    print("  " + "-" * 52)

    best_single_acc  = 0.0
    best_single_name = ""

    for col, label in SIGNAL_NAMES.items():
        stats = results[col]
        acc   = stats["accuracy"]
        sigs  = stats["signals"]
        neut  = stats["neutral_pct"]
        print(f"  {label:<18} {acc*100:>9.1f}%  {sigs:>8}  {neut*100:>8.0f}%")
        if col != "sig_combined" and acc > best_single_acc:
            best_single_acc  = acc
            best_single_name = label

    combined_acc = results["sig_combined"]["accuracy"]
    print()
    print(f"  Random baseline:  50.0%")
    print(f"  Best single:      {best_single_name} ({best_single_acc*100:.1f}%)")
    print(f"  Best combined:    {combined_acc*100:.1f}%")
    print()
    print(f"  Verdict: {verdict(combined_acc)}")
    print("=" * 56)


# ── Charting ──────────────────────────────────────────────────────────────────

def make_chart(symbol: str, results: dict, df_rows: pd.DataFrame, timestamp_str: str):
    labels    = [SIGNAL_NAMES[c] for c in SIGNAL_NAMES]
    accuracies = [results[c]["accuracy"] * 100 for c in SIGNAL_NAMES]
    signals    = [results[c]["signals"]        for c in SIGNAL_NAMES]

    fig = plt.figure(figsize=(16, 12), facecolor="#1a1a2e")
    fig.suptitle(
        f"Backtest 2: Technical Indicator Signals — {symbol}\n"
        f"{DAYS}d | {STEP_HOURS}h step | {LOOKAHEAD}-bar lookahead",
        color="white", fontsize=14, fontweight="bold", y=0.98
    )

    gs = gridspec.GridSpec(3, 1, figure=fig, hspace=0.45)

    ax_colors = ["#16213e", "#0f3460", "#1a1a2e"]
    bar_colors = ["#e94560" if a < 50 else "#00d4aa" for a in accuracies]

    # ── Subplot 1: Accuracy bar chart ──
    ax1 = fig.add_subplot(gs[0])
    ax1.set_facecolor(ax_colors[0])
    bars = ax1.bar(labels, accuracies, color=bar_colors, edgecolor="#ffffff22", linewidth=0.5)
    ax1.axhline(50, color="#ff6b6b", linestyle="--", linewidth=1.5, label="50% baseline", alpha=0.8)
    ax1.set_ylabel("Accuracy (%)", color="white")
    ax1.set_title("Signal Accuracy", color="white", fontsize=11)
    ax1.tick_params(colors="white", axis="both")
    ax1.spines[["top", "right"]].set_visible(False)
    ax1.spines[["left", "bottom"]].set_color("#555555")
    ax1.set_ylim(45, 65)
    ax1.legend(facecolor="#2a2a4e", labelcolor="white", framealpha=0.7)
    for bar, acc in zip(bars, accuracies):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                 f"{acc:.1f}%", ha="center", va="bottom", color="white", fontsize=9)
    plt.setp(ax1.xaxis.get_majorticklabels(), rotation=20, ha="right", fontsize=9)

    # ── Subplot 2: Signal count vs accuracy scatter ──
    ax2 = fig.add_subplot(gs[1])
    ax2.set_facecolor(ax_colors[1])
    scatter_colors = ["#00d4aa", "#e94560", "#ffd700", "#c77dff", "#48cae4", "#f77f00"]
    for i, (label, sig_count, acc) in enumerate(zip(labels, signals, accuracies)):
        ax2.scatter(sig_count, acc, s=120, color=scatter_colors[i % len(scatter_colors)],
                    zorder=3, edgecolors="white", linewidths=0.5)
        ax2.annotate(label, (sig_count, acc), textcoords="offset points",
                     xytext=(8, 3), color="white", fontsize=8)
    ax2.axhline(50, color="#ff6b6b", linestyle="--", linewidth=1.2, alpha=0.7)
    ax2.set_xlabel("Number of Non-Neutral Signals", color="white")
    ax2.set_ylabel("Accuracy (%)", color="white")
    ax2.set_title("Signal Count vs Accuracy", color="white", fontsize=11)
    ax2.tick_params(colors="white", axis="both")
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.spines[["left", "bottom"]].set_color("#555555")

    # ── Subplot 3: Rolling accuracy of combined signal ──
    ax3 = fig.add_subplot(gs[2])
    ax3.set_facecolor(ax_colors[2])
    rolled = rolling_accuracy(df_rows, "sig_combined", window=50)
    if not rolled.empty:
        ax3.plot(rolled.index, rolled * 100, color="#00d4aa", linewidth=1.5,
                 label="Rolling 50-window accuracy")
        ax3.axhline(50, color="#ff6b6b", linestyle="--", linewidth=1.2, alpha=0.7, label="50% baseline")
        ax3.fill_between(rolled.index, 50, rolled * 100,
                         where=(rolled * 100 >= 50), alpha=0.15, color="#00d4aa")
        ax3.fill_between(rolled.index, 50, rolled * 100,
                         where=(rolled * 100 < 50), alpha=0.15, color="#e94560")
    ax3.set_xlabel("Time", color="white")
    ax3.set_ylabel("Rolling Accuracy (%)", color="white")
    ax3.set_title("Combined Signal: Rolling 50-Window Accuracy", color="white", fontsize=11)
    ax3.tick_params(colors="white", axis="both")
    ax3.spines[["top", "right"]].set_visible(False)
    ax3.spines[["left", "bottom"]].set_color("#555555")
    ax3.legend(facecolor="#2a2a4e", labelcolor="white", framealpha=0.7)
    plt.setp(ax3.xaxis.get_majorticklabels(), rotation=15, ha="right", fontsize=8)

    chart_path = RESULTS_DIR / f"backtest_2_quant_{timestamp_str}.png"
    fig.savefig(chart_path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Chart saved: {chart_path}")
    return chart_path


# ── CSV export ────────────────────────────────────────────────────────────────

def save_csv(symbol: str, results: dict, df_rows: pd.DataFrame):
    csv_path = RESULTS_DIR / f"{symbol}_backtest2.csv"
    df_rows.to_csv(csv_path, index=False)
    print(f"  CSV  saved: {csv_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def run_symbol(symbol: str, timestamp_str: str):
    print(f"\n{'─'*56}")
    print(f"  Symbol: {symbol}")
    df = fetch_klines(symbol, DAYS)
    print(f"  Computing indicators...")
    df = compute_signals(df)
    print(f"  Evaluating signals (lookahead={LOOKAHEAD} bars, step={STEP_HOURS}h)...")
    results, df_rows = evaluate(df, STEP_HOURS, LOOKAHEAD)
    print_report(symbol, results)
    make_chart(symbol, results, df_rows, f"{symbol}_{timestamp_str}")
    save_csv(symbol, results, df_rows)
    return results


def main():
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print("\n" + "=" * 56)
    print("  Backtest 2: Technical Indicator Signals")
    print(f"  Symbols: {', '.join(SYMBOLS)}")
    print(f"  Period: {DAYS} days | Step: {STEP_HOURS}h | Lookahead: {LOOKAHEAD} bars")
    print("=" * 56)

    all_results = {}
    for symbol in SYMBOLS:
        all_results[symbol] = run_symbol(symbol, timestamp_str)

    # Summary across symbols
    if len(SYMBOLS) > 1:
        print("\n" + "=" * 56)
        print("  Multi-Symbol Summary")
        print("=" * 56)
        for symbol, results in all_results.items():
            comb_acc = results["sig_combined"]["accuracy"] * 100
            print(f"  {symbol:<12} combined={comb_acc:.1f}%  {verdict(results['sig_combined']['accuracy'])}")
        print("=" * 56)

    print("\nDone.\n")


if __name__ == "__main__":
    main()
