"""
backtest_6_walkforward.py — Walk-Forward Validation of KronosModel
===================================================================
Splits 90 days of 1m klines into 3 overlapping train/test folds,
runs Kronos on each test period, and checks whether accuracy degrades
fold-to-fold (overfitting / distribution-shift signal).

Fold design (days):
  Fold 1: train 0-60  -> test 60-90
  Fold 2: train 10-70 -> test 70-90
  Fold 3: train 20-80 -> test 80-90

Kronos is zero-shot (no training), so the "train" window just sets
the temporal context.  We compare test-period accuracy across folds.

Usage:
  cd AI_Trading
  source backend/.venv/bin/activate
  python backend/scripts/backtest_6_walkforward.py
"""

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import httpx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

# ── Settings ──────────────────────────────────────────────────────────────────
SYMBOL     = "BTCUSDT"
DAYS       = 90
STEP_HOURS = 4
SL_PCT     = 0.02
TP_PCT     = 0.04
SEQ_LEN    = 512
PRED_LEN   = 60
RESULTS_DIR = Path(__file__).parent.parent / "backtest_results"
RESULTS_DIR.mkdir(exist_ok=True)

# Walk-forward fold definitions: (train_start_day, train_end_day, test_end_day)
FOLDS = [
    (0,  60, 90),
    (10, 70, 90),
    (20, 80, 90),
]

# ── Import path ────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ── Binance kline downloader ──────────────────────────────────────────────────
BINANCE_BASE = "https://fapi.binance.com"


def fetch_klines_binance(symbol: str, days: int) -> pd.DataFrame:
    """Download 1m klines from Binance futures public API (no key needed)."""
    print(f"  Downloading {symbol} ({days}d of 1m klines)...", end="", flush=True)
    end_ms   = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    start_ms = end_ms - days * 24 * 3600 * 1000
    all_rows = []
    limit    = 1000

    with httpx.Client(timeout=30) as client:
        cur = start_ms
        while cur < end_ms:
            resp = client.get(
                f"{BINANCE_BASE}/fapi/v1/klines",
                params={
                    "symbol":    symbol,
                    "interval":  "1m",
                    "startTime": cur,
                    "endTime":   end_ms,
                    "limit":     limit,
                },
            )
            resp.raise_for_status()
            rows = resp.json()
            if not rows:
                break
            all_rows.extend(rows)
            cur = rows[-1][0] + 60_000
            print(".", end="", flush=True)
            time.sleep(0.05)

    df = pd.DataFrame(all_rows, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_vol", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore",
    ])
    df["ts"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df = df.set_index("ts").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    print(f" {len(df):,} bars")
    return df[["open", "high", "low", "close", "volume"]]


# ── Kronos loader ─────────────────────────────────────────────────────────────
def load_kronos():
    print("  Loading KronosModel (may take ~30s on first run)...")
    from cryptoswarm.ml.kronos_model import KronosModel
    model = KronosModel(pred_len=PRED_LEN, max_context=SEQ_LEN, verbose=False)
    model._ensure_loaded()
    print("  KronosModel loaded.")
    return model


def run_kronos_window(model, window_df: pd.DataFrame):
    """Run Kronos on one window. Returns (regime, direction, short_dir, conf) or None."""
    klines = window_df[["open", "high", "low", "close", "volume"]].to_dict("records")
    try:
        regime, direction, short_dir, conf = model.predict(klines, interval_minutes=1)
        return regime, direction, short_dir, conf
    except Exception:
        return None


# ── Trade simulation ──────────────────────────────────────────────────────────
def simulate_trade(future_bars: pd.DataFrame, side: str, entry: float) -> dict:
    sl = entry * (1 - SL_PCT) if side == "long" else entry * (1 + SL_PCT)
    tp = entry * (1 + TP_PCT) if side == "long" else entry * (1 - TP_PCT)

    for i, (_, row) in enumerate(future_bars.iterrows()):
        high, low = row["high"], row["low"]
        if side == "long":
            if low  <= sl: return {"outcome": "sl", "pnl_pct": -SL_PCT, "bars": i + 1}
            if high >= tp: return {"outcome": "tp", "pnl_pct": +TP_PCT, "bars": i + 1}
        else:
            if high >= sl: return {"outcome": "sl", "pnl_pct": -SL_PCT, "bars": i + 1}
            if low  <= tp: return {"outcome": "tp", "pnl_pct": +TP_PCT, "bars": i + 1}

    exit_price = future_bars["close"].iloc[-1] if len(future_bars) > 0 else entry
    pnl = (exit_price - entry) / entry if side == "long" else (entry - exit_price) / entry
    return {"outcome": "timeout", "pnl_pct": pnl, "bars": len(future_bars)}


# ── Single-fold backtest ──────────────────────────────────────────────────────
def backtest_fold(
    fold_num: int,
    test_df: pd.DataFrame,
    model,
) -> pd.DataFrame:
    """Run Kronos on test_df using sliding windows."""
    print(f"\n  Fold {fold_num}: {len(test_df):,} bars in test window...")
    step_bars     = STEP_HOURS * 60
    results       = []
    total_windows = max((len(test_df) - SEQ_LEN - PRED_LEN) // step_bars, 1)

    i          = SEQ_LEN
    window_num = 0
    while i + PRED_LEN < len(test_df):
        window_num += 1
        if window_num % 10 == 0:
            pct = window_num / total_windows * 100
            print(f"    [{pct:.0f}%] window {window_num}/{total_windows}", end="\r")

        window   = test_df.iloc[i - SEQ_LEN : i]
        future   = test_df.iloc[i : i + PRED_LEN]
        entry_ts = test_df.index[i]
        entry_px = test_df["close"].iloc[i]

        result = run_kronos_window(model, window)
        if result is None:
            i += step_bars
            continue

        regime, direction, short_dir, conf = result

        future_close = test_df["close"].iloc[min(i + PRED_LEN, len(test_df) - 1)]
        actual_dir   = "up" if future_close > entry_px else "down"
        dir_correct  = (direction == actual_dir)

        side  = "long" if direction == "up" else "short"
        trade = simulate_trade(future, side, entry_px)

        results.append({
            "fold":             fold_num,
            "ts":               entry_ts,
            "entry_price":      entry_px,
            "regime":           regime,
            "pred_direction":   direction,
            "confidence":       conf,
            "actual_direction": actual_dir,
            "dir_correct":      dir_correct,
            "trade_outcome":    trade["outcome"],
            "trade_pnl_pct":    trade["pnl_pct"],
            "bars_held":        trade["bars"],
        })
        i += step_bars

    print(f"    Done — {len(results)} windows.         ")
    return pd.DataFrame(results)


# ── Report ────────────────────────────────────────────────────────────────────
def print_fold_report(fold_results: list[dict]):
    print(f"\n{'='*60}")
    print("  Walk-Forward Validation — Per-Fold Results")
    print(f"{'='*60}")
    print(f"  {'Fold':<8} {'Test Period':<26} {'Windows':>7} {'Accuracy':>9} {'Win%':>7} {'Loss%':>7} {'P&L%':>9}")
    print(f"  {'-'*75}")
    for r in fold_results:
        print(
            f"  {r['fold_label']:<8} "
            f"{r['test_start']} -> {r['test_end']}  "
            f"{r['windows']:>7}  "
            f"{r['accuracy']:>7.1f}%  "
            f"{r['tp_rate']:>5.1f}%  "
            f"{r['sl_rate']:>5.1f}%  "
            f"{r['total_pnl']:>+7.1f}%"
        )
    print(f"{'='*60}")

    accs = [r["accuracy"] for r in fold_results]
    if len(accs) >= 2:
        drift = accs[-1] - accs[0]
        if abs(drift) < 2:
            signal = "STABLE (no significant drift)"
        elif drift < 0:
            signal = f"DEGRADING ({drift:+.1f}% drift — possible distribution shift)"
        else:
            signal = f"IMPROVING ({drift:+.1f}% drift)"
        print(f"\n  Overfitting signal: {signal}")
    print()


# ── Chart ─────────────────────────────────────────────────────────────────────
def plot_walkforward(fold_results: list[dict], fold_dfs: list[pd.DataFrame], out_path: Path):
    """Fold comparison chart with 4 panels."""
    fig = plt.figure(figsize=(16, 10), facecolor="#0d1117")
    fig.suptitle("Kronos Walk-Forward Validation (3 Folds)", color="white",
                 fontsize=14, fontweight="bold")
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.32)

    fold_labels = [r["fold_label"] for r in fold_results]
    fold_colors = ["#58a6ff", "#f2a900", "#3fb950"]

    # Panel 1: Accuracy per fold
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.set_facecolor("#161b22")
    ax1.set_title("Direction Accuracy per Fold", color="white", fontsize=11)
    accs  = [r["accuracy"] for r in fold_results]
    bars1 = ax1.bar(range(len(fold_results)), accs,
                    color=fold_colors[:len(fold_results)], alpha=0.85, width=0.5)
    ax1.axhline(50, color="#f85149", linewidth=1.2, linestyle="--", label="50% baseline")
    ax1.set_xticks(range(len(fold_results)))
    ax1.set_xticklabels(fold_labels, color="#8b949e", fontsize=10)
    ax1.set_ylabel("Accuracy %", color="#8b949e", fontsize=9)
    ax1.tick_params(colors="#8b949e")
    ax1.spines[:].set_color("#30363d")
    ax1.set_ylim(0, 85)
    ax1.legend(facecolor="#161b22", labelcolor="white", fontsize=9)
    for bar, val in zip(bars1, accs):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                 f"{val:.1f}%", ha="center", color="white", fontsize=9)

    # Panel 2: Total P&L per fold
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_facecolor("#161b22")
    ax2.set_title("Total Simulated P&L per Fold", color="white", fontsize=11)
    pnls  = [r["total_pnl"] for r in fold_results]
    bcolors = ["#3fb950" if p >= 0 else "#f85149" for p in pnls]
    bars2 = ax2.bar(range(len(fold_results)), pnls, color=bcolors, alpha=0.85, width=0.5)
    ax2.axhline(0, color="#30363d", linewidth=0.8)
    ax2.set_xticks(range(len(fold_results)))
    ax2.set_xticklabels(fold_labels, color="#8b949e", fontsize=10)
    ax2.set_ylabel("Total P&L %", color="#8b949e", fontsize=9)
    ax2.tick_params(colors="#8b949e")
    ax2.spines[:].set_color("#30363d")
    for bar, val in zip(bars2, pnls):
        ax2.text(bar.get_x() + bar.get_width() / 2,
                 bar.get_height() + (0.5 if val >= 0 else -2.5),
                 f"{val:+.1f}%", ha="center", color="white", fontsize=9)

    # Panel 3: Win / Loss rate per fold
    ax3 = fig.add_subplot(gs[1, 0])
    ax3.set_facecolor("#161b22")
    ax3.set_title("TP / SL / Timeout Rate per Fold", color="white", fontsize=11)
    x    = np.arange(len(fold_results))
    w    = 0.25
    tp_r = [r["tp_rate"] for r in fold_results]
    sl_r = [r["sl_rate"] for r in fold_results]
    to_r = [r["timeout_rate"] for r in fold_results]
    ax3.bar(x - w, tp_r,  width=w, label="TP",      color="#3fb950", alpha=0.85)
    ax3.bar(x,     sl_r,  width=w, label="SL",      color="#f85149", alpha=0.85)
    ax3.bar(x + w, to_r,  width=w, label="Timeout", color="#8b949e", alpha=0.85)
    ax3.set_xticks(x)
    ax3.set_xticklabels(fold_labels, color="#8b949e", fontsize=10)
    ax3.set_ylabel("Rate %", color="#8b949e", fontsize=9)
    ax3.tick_params(colors="#8b949e")
    ax3.spines[:].set_color("#30363d")
    ax3.legend(facecolor="#161b22", labelcolor="white", fontsize=9)

    # Panel 4: Cumulative P&L curves per fold
    ax4 = fig.add_subplot(gs[1, 1])
    ax4.set_facecolor("#161b22")
    ax4.set_title("Cumulative P&L Curve per Fold", color="white", fontsize=11)
    for i, (df, label) in enumerate(zip(fold_dfs, fold_labels)):
        if df.empty:
            continue
        cum = df["trade_pnl_pct"].cumsum() * 100
        ax4.plot(range(len(cum)), cum, label=label,
                 color=fold_colors[i % len(fold_colors)], linewidth=1.5)
    ax4.axhline(0, color="#30363d", linewidth=0.8)
    ax4.set_xlabel("Trade #", color="#8b949e", fontsize=9)
    ax4.set_ylabel("Cumulative P&L %", color="#8b949e", fontsize=9)
    ax4.tick_params(colors="#8b949e")
    ax4.spines[:].set_color("#30363d")
    ax4.legend(facecolor="#161b22", labelcolor="white", fontsize=9)

    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    print(f"  Chart saved: {out_path}")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    print("\n" + "=" * 60)
    print("  Kronos Walk-Forward Validation")
    print(f"  Symbol: {SYMBOL}  |  {DAYS} days of 1m klines")
    print(f"  Folds : {len(FOLDS)}  |  Step: {STEP_HOURS}h  |  Pred: {PRED_LEN} bars")
    print(f"  SL: {SL_PCT*100:.0f}%  TP: {TP_PCT*100:.0f}%")
    print("=" * 60 + "\n")

    # 1. Download all 90d of data
    print("Step 1/3: Downloading historical data...")
    full_df = fetch_klines_binance(SYMBOL, DAYS)

    # 2. Load Kronos
    print("\nStep 2/3: Loading KronosModel...")
    model = load_kronos()

    # 3. Run each fold
    print("\nStep 3/3: Running walk-forward folds...")
    bars_per_day  = 24 * 60   # 1m bars
    total_bars    = len(full_df)

    fold_results  = []
    fold_dfs      = []

    for fold_idx, (train_start_d, train_end_d, test_end_d) in enumerate(FOLDS, start=1):
        # Compute bar indices for the TEST window
        # We run Kronos on the test window (the model sees SEQ_LEN bars of context
        # from within the test window itself).
        test_start_bar = int((train_end_d / DAYS) * total_bars)
        test_end_bar   = int((test_end_d  / DAYS) * total_bars)
        test_df        = full_df.iloc[test_start_bar:test_end_bar].copy()

        test_start_str = test_df.index[0].date() if len(test_df) else "N/A"
        test_end_str   = test_df.index[-1].date() if len(test_df) else "N/A"
        label          = f"Fold {fold_idx}"

        print(f"\n{'─'*50}")
        print(f"  {label}: train day {train_start_d}-{train_end_d} | "
              f"test day {train_end_d}-{test_end_d} "
              f"({test_start_str} -> {test_end_str})")

        t0      = time.time()
        fold_df = backtest_fold(fold_idx, test_df, model)
        elapsed = time.time() - t0
        print(f"  Fold {fold_idx} done in {elapsed/60:.1f} min")

        fold_dfs.append(fold_df)

        if fold_df.empty:
            fold_results.append({
                "fold_label":   label,
                "test_start":   str(test_start_str),
                "test_end":     str(test_end_str),
                "windows":      0,
                "accuracy":     0.0,
                "tp_rate":      0.0,
                "sl_rate":      0.0,
                "timeout_rate": 0.0,
                "total_pnl":    0.0,
                "avg_pnl":      0.0,
            })
            continue

        accuracy     = fold_df["dir_correct"].mean() * 100
        tp_rate      = (fold_df["trade_outcome"] == "tp").mean() * 100
        sl_rate      = (fold_df["trade_outcome"] == "sl").mean() * 100
        timeout_rate = (fold_df["trade_outcome"] == "timeout").mean() * 100
        total_pnl    = fold_df["trade_pnl_pct"].sum() * 100
        avg_pnl      = fold_df["trade_pnl_pct"].mean() * 100

        fold_results.append({
            "fold_label":   label,
            "test_start":   str(test_start_str),
            "test_end":     str(test_end_str),
            "windows":      len(fold_df),
            "accuracy":     accuracy,
            "tp_rate":      tp_rate,
            "sl_rate":      sl_rate,
            "timeout_rate": timeout_rate,
            "total_pnl":    total_pnl,
            "avg_pnl":      avg_pnl,
        })

    # 4. Print consolidated report
    print_fold_report(fold_results)

    # 5. Save combined CSV
    all_df    = pd.concat(fold_dfs, ignore_index=True) if fold_dfs else pd.DataFrame()
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path  = RESULTS_DIR / f"walkforward_{SYMBOL}_{ts}.csv"
    if not all_df.empty:
        all_df.to_csv(csv_path, index=False)
        print(f"  Combined results saved: {csv_path}")

    # 6. Save chart
    chart_path = RESULTS_DIR / f"backtest_6_walkforward_{ts}.png"
    print("\nGenerating chart...")
    plot_walkforward(fold_results, fold_dfs, chart_path)

    print("\nDone. Results in:", RESULTS_DIR)


if __name__ == "__main__":
    main()
