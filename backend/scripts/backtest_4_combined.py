"""
Backtest 4: Signal Agreement Analysis
Tests whether multi-signal agreement improves win rate on 1h BTC klines.
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
import httpx
import ta

# ── Settings ──────────────────────────────────────────────────────────────────
SYMBOL           = "BTCUSDT"
DAYS             = 90
LOOKAHEAD_HOURS  = 4
MAX_KLINES       = 1000   # Binance per-request limit

# ── Output dir ────────────────────────────────────────────────────────────────
RESULTS_DIR = Path(__file__).resolve().parent.parent / "backtest_results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Dark theme ────────────────────────────────────────────────────────────────
BG      = "#0d1117"
SURFACE = "#161b22"
GRID    = "#30363d"
TEXT    = "#c9d1d9"
ACCENT1 = "#58a6ff"
ACCENT2 = "#f78166"
GREEN   = "#3fb950"
YELLOW  = "#d29922"


def fetch_1h_klines(symbol: str, days: int) -> pd.DataFrame:
    """Fetch 1h Binance klines for `days` days, paging if needed."""
    end_ms   = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    start_ms = end_ms - days * 24 * 3600 * 1000

    url     = "https://fapi.binance.com/fapi/v1/klines"
    all_bars: list = []
    cursor  = start_ms

    print(f"[DATA] Fetching {days}d of 1h {symbol} klines from Binance Futures…")
    with httpx.Client(timeout=30) as client:
        while cursor < end_ms:
            params = {
                "symbol":    symbol,
                "interval":  "1h",
                "startTime": cursor,
                "endTime":   end_ms,
                "limit":     MAX_KLINES,
            }
            resp = client.get(url, params=params)
            resp.raise_for_status()
            bars = resp.json()
            if not bars:
                break
            all_bars.extend(bars)
            last_ts = int(bars[-1][0])
            if last_ts <= cursor:
                break
            cursor = last_ts + 1
            print(f"[DATA]   …fetched {len(all_bars)} bars so far")

    rows = []
    for bar in all_bars:
        rows.append({
            "ts":     pd.Timestamp(bar[0], unit="ms", tz="UTC"),
            "open":   float(bar[1]),
            "high":   float(bar[2]),
            "low":    float(bar[3]),
            "close":  float(bar[4]),
            "volume": float(bar[5]),
        })

    df = pd.DataFrame(rows).drop_duplicates("ts").sort_values("ts").reset_index(drop=True)
    print(f"[DATA] Total bars: {len(df)}  ({df['ts'].iloc[0]} → {df['ts'].iloc[-1]})")
    return df


def compute_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Add 5 binary signals and agreement score."""
    print("[SIG ] Computing technical indicators…")
    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    volume = df["volume"]

    # 1. RSI momentum
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi()
    sig_rsi = pd.Series(0, index=df.index)
    sig_rsi[rsi > 55] =  1
    sig_rsi[rsi < 45] = -1

    # 2. MACD histogram
    macd_obj  = ta.trend.MACD(close)
    macd_hist = macd_obj.macd_diff()
    sig_macd = (macd_hist > 0).astype(int) * 2 - 1   # +1 / -1

    # 3. EMA cross (20 vs 50)
    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator()
    sig_ema = ((ema20 > ema50).astype(int) * 2 - 1)

    # 4. Bollinger Band position (price vs midband)
    bb     = ta.volatility.BollingerBands(close, window=20)
    mid    = bb.bollinger_mavg()
    sig_bb = ((close > mid).astype(int) * 2 - 1)

    # 5. Volume confirmation (volume > 20-bar avg)
    vol_avg  = volume.rolling(20).mean()
    sig_vol  = pd.Series(0, index=df.index)
    sig_vol[volume > vol_avg] = 1   # confirm; 0 = no confirmation

    df = df.copy()
    df["sig_rsi"]  = sig_rsi
    df["sig_macd"] = sig_macd
    df["sig_ema"]  = sig_ema
    df["sig_bb"]   = sig_bb
    df["sig_vol"]  = sig_vol

    # Score: sum of 4 directional signals (-4 to +4), then volume acts as
    # a ±1 bonus in the direction of the score to reach ±5
    base_score = df[["sig_rsi", "sig_macd", "sig_ema", "sig_bb"]].sum(axis=1)
    vol_bonus  = df["sig_vol"] * base_score.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    df["score"] = (base_score + vol_bonus).clip(-5, 5).astype(int)

    # Future return
    df["ret_future"] = df["close"].shift(-LOOKAHEAD_HOURS) / df["close"] - 1
    df["dir_future"] = (df["ret_future"] > 0).astype(int)

    df = df.dropna(subset=["ret_future"]).reset_index(drop=True)
    print(f"[SIG ] Signal computation done — {len(df)} usable bars")
    return df


def analyse_agreement(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for score in range(-5, 6):
        sub = df[df["score"] == score]
        if len(sub) == 0:
            rows.append({"score": score, "count": 0, "accuracy": float("nan"), "avg_pnl": float("nan")})
            continue
        # predicted direction
        pred = 1 if score > 0 else (-1 if score < 0 else 0)
        if pred == 0:
            correct = pd.Series([False] * len(sub))
            acc = float("nan")
        else:
            correct = (sub["dir_future"] == (1 if pred == 1 else 0))
            acc = correct.mean()
        avg_pnl = (sub["ret_future"] * pred).mean() * 100
        rows.append({"score": score, "count": len(sub), "accuracy": acc, "avg_pnl": avg_pnl})
    return pd.DataFrame(rows)


def print_report(agg_df: pd.DataFrame) -> None:
    strong = agg_df[agg_df["score"].abs() >= 4]
    weak   = agg_df[agg_df["score"].abs() <  4]

    def weighted_acc(sub_df: pd.DataFrame) -> float:
        sub_df = sub_df.dropna(subset=["accuracy"])
        if len(sub_df) == 0 or sub_df["count"].sum() == 0:
            return float("nan")
        return (sub_df["accuracy"] * sub_df["count"]).sum() / sub_df["count"].sum()

    strong_acc = weighted_acc(strong)
    weak_acc   = weighted_acc(weak)
    strong_n   = int(strong["count"].sum())
    weak_n     = int(weak["count"].sum())

    labels = {
        -5: "All SHORT",
        5:  "All LONG",
    }
    noise_scores = {-2, -1, 0, 1, 2}

    print()
    print("=====================================")
    print("  Backtest 4: Signal Agreement Analysis")
    print("=====================================")
    header = f"  {'Agreement':<14} {'Count':>6}   {'Accuracy':>9}   {'Avg P&L':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for _, row in agg_df.iterrows():
        sc = int(row["score"])
        label = labels.get(sc, str(sc))
        acc_str = f"{row['accuracy']*100:.1f}%" if not np.isnan(row["accuracy"]) else "  N/A"
        pnl_str = f"{row['avg_pnl']:+.1f}%" if not np.isnan(row["avg_pnl"]) else "  N/A"
        noise_mark = "  ← noise zone" if sc in noise_scores else ""
        print(f"  {label:<14} {int(row['count']):>6}   {acc_str:>9}   {pnl_str:>8}{noise_mark}")
    print()
    print(f"  Key finding: accuracy jumps when |score| >= 4")
    strong_acc_str = f"{strong_acc*100:.1f}%" if not np.isnan(strong_acc) else "N/A"
    weak_acc_str   = f"{weak_acc*100:.1f}%"   if not np.isnan(weak_acc)   else "N/A"
    print(f"  Strong signal (|score|>=4) accuracy: {strong_acc_str}  n={strong_n}")
    print(f"  Weak signal  (|score|<4)  accuracy: {weak_acc_str}  n={weak_n}")
    print("=====================================")


def make_chart(agg_df: pd.DataFrame, out_path: Path) -> None:
    print("[CHART] Generating chart…")
    fig = plt.figure(figsize=(14, 7), facecolor=BG)
    ax = fig.add_subplot(111)
    ax.set_facecolor(SURFACE)
    ax.tick_params(colors=TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)
    ax.grid(color=GRID, linestyle="--", linewidth=0.5, alpha=0.7, axis="y")

    scores      = agg_df["score"].tolist()
    accs        = [(v * 100 if not np.isnan(v) else 0) for v in agg_df["accuracy"]]
    counts      = agg_df["count"].tolist()

    # Color bars by agreement direction
    bar_colors = []
    for sc in scores:
        if sc <= -4:
            bar_colors.append(ACCENT2)
        elif sc < -2:
            bar_colors.append("#f0883e")
        elif sc in (-2, -1, 0, 1, 2):
            bar_colors.append(YELLOW)
        elif sc < 5:
            bar_colors.append("#56d364")
        else:
            bar_colors.append(GREEN)

    x = np.arange(len(scores))
    width = 0.6
    bars = ax.bar(x, accs, width=width, color=bar_colors, alpha=0.85,
                  edgecolor=GRID, linewidth=0.8, label="Accuracy (%)")
    ax.axhline(50, color=TEXT, linestyle="--", linewidth=1.2, alpha=0.7, label="50% baseline")

    # Count overlay on secondary y-axis
    ax2 = ax.twinx()
    ax2.set_facecolor(SURFACE)
    ax2.tick_params(colors=TEXT)
    ax2.plot(x, counts, color=ACCENT1, linewidth=1.5, marker="o", markersize=4,
             label="Count", alpha=0.8)
    ax2.set_ylabel("Count", color=ACCENT1, fontsize=10)
    ax2.tick_params(axis="y", colors=ACCENT1)
    for spine in ax2.spines.values():
        spine.set_edgecolor(GRID)

    # Annotate accuracy on each bar
    for bar_rect, acc in zip(bars, accs):
        if acc > 0:
            ax.text(
                bar_rect.get_x() + bar_rect.get_width() / 2,
                bar_rect.get_height() + 0.3,
                f"{acc:.1f}%",
                ha="center", va="bottom", fontsize=7.5, color=TEXT,
            )

    ax.set_xticks(x)
    ax.set_xticklabels([str(s) for s in scores], color=TEXT)
    ax.set_xlabel("Agreement Score (-5 = all SHORT … +5 = all LONG)", fontsize=10, color=TEXT)
    ax.set_ylabel("Accuracy (%)", fontsize=10, color=TEXT)
    ax.set_ylim(30, 75)
    ax.title.set_color(TEXT)
    ax.set_title(
        f"Signal Agreement vs Win Rate  (BTC/USDT 1h, {LOOKAHEAD_HOURS}h lookahead)",
        fontsize=12, pad=10, color=TEXT,
    )

    # Combined legend
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2,
              facecolor=SURFACE, edgecolor=GRID, labelcolor=TEXT, fontsize=8)

    fig.suptitle("Backtest 4 — Multi-Signal Agreement Analysis", fontsize=14,
                 color=TEXT, y=0.98, facecolor=BG)
    fig.patch.set_facecolor(BG)

    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[CHART] Saved → {out_path}")


def main() -> None:
    df      = fetch_1h_klines(SYMBOL, DAYS)
    df      = compute_signals(df)
    agg_df  = analyse_agreement(df)

    print_report(agg_df)

    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"backtest_4_combined_{ts}.png"
    make_chart(agg_df, out_path)

    print("\n[DONE] Backtest 4 complete.")


if __name__ == "__main__":
    main()
