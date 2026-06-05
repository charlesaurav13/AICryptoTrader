"""
Backtest 3: Sentiment Correlation
Tests whether Fear & Greed index predicts BTC next-day price direction.
"""

import sys
import json
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd
import httpx

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

# ── FNG zone definitions ──────────────────────────────────────────────────────
ZONES = [
    ("Extreme Fear",  0,  25),
    ("Fear",         26,  49),
    ("Neutral",      50,  55),
    ("Greed",        56,  74),
    ("Extreme Greed",75, 100),
]


def fetch_fng(limit: int = 365) -> pd.DataFrame:
    url = f"https://api.alternative.me/fng/?limit={limit}&format=json"
    print(f"[FNG ] Fetching Fear & Greed history ({limit} days)…")
    with httpx.Client(timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
    data = resp.json()["data"]
    rows = []
    for item in data:
        rows.append({
            "date": datetime.fromtimestamp(int(item["timestamp"]), tz=timezone.utc).date(),
            "fng":  int(item["value"]),
            "label": item["value_classification"],
        })
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    print(f"[FNG ] Got {len(df)} rows  ({df['date'].min().date()} → {df['date'].max().date()})")
    return df


def fetch_btc_daily(limit: int = 365) -> pd.DataFrame:
    url = (
        "https://fapi.binance.com/fapi/v1/klines"
        f"?symbol=BTCUSDT&interval=1d&limit={limit}"
    )
    print(f"[BTC ] Fetching Binance daily klines ({limit} bars)…")
    with httpx.Client(timeout=30) as client:
        resp = client.get(url)
        resp.raise_for_status()
    raw = resp.json()
    rows = []
    for bar in raw:
        rows.append({
            "date":  pd.Timestamp(bar[0], unit="ms", tz="UTC").normalize(),
            "open":  float(bar[1]),
            "close": float(bar[4]),
        })
    df = pd.DataFrame(rows)
    df = df.sort_values("date").reset_index(drop=True)
    print(f"[BTC ] Got {len(df)} rows  ({df['date'].min().date()} → {df['date'].max().date()})")
    return df


def zone_label(fng: int) -> str:
    for name, lo, hi in ZONES:
        if lo <= fng <= hi:
            return name
    return "Unknown"


def build_dataset(fng_df: pd.DataFrame, btc_df: pd.DataFrame) -> pd.DataFrame:
    """Merge FNG with BTC and compute next-day return."""
    print("[DATA] Merging FNG & BTC data…")
    fng_df = fng_df.copy()
    fng_df["date"] = pd.to_datetime(fng_df["date"]).dt.tz_localize("UTC")

    btc_df = btc_df.copy()
    btc_df["ret_next"] = btc_df["close"].shift(-1) / btc_df["close"] - 1
    btc_df["dir_next"] = (btc_df["ret_next"] > 0).astype(int)  # 1 = up, 0 = down

    merged = pd.merge(fng_df, btc_df[["date", "close", "ret_next", "dir_next"]], on="date", how="inner")
    merged = merged.dropna(subset=["ret_next"])
    merged["zone"] = merged["fng"].apply(zone_label)

    # FNG 3-day momentum
    merged["fng_mom3"] = merged["fng"].diff(3)

    print(f"[DATA] Final dataset: {len(merged)} rows")
    return merged


def analyse_zones(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, lo, hi in ZONES:
        sub = df[(df["fng"] >= lo) & (df["fng"] <= hi)]
        if len(sub) == 0:
            rows.append({"zone": name, "count": 0, "accuracy": float("nan"), "avg_ret": float("nan")})
            continue
        acc = sub["dir_next"].mean()
        avg = sub["ret_next"].mean()
        rows.append({"zone": name, "count": len(sub), "accuracy": acc, "avg_ret": avg})
    return pd.DataFrame(rows)


def contrarian_strategy(df: pd.DataFrame) -> dict:
    """Long when FNG < 30, short when FNG > 70, else hold."""
    results = []
    equity_contrarian = [1.0]
    equity_bh = [1.0]

    for _, row in df.iterrows():
        fng = row["fng"]
        ret = row["ret_next"]

        # Buy-and-hold
        equity_bh.append(equity_bh[-1] * (1 + ret))

        # Contrarian
        if fng < 30:
            pos = 1
        elif fng > 70:
            pos = -1
        else:
            pos = 0
        strat_ret = pos * ret
        equity_contrarian.append(equity_contrarian[-1] * (1 + strat_ret))

        correct = (pos == 1 and ret > 0) or (pos == -1 and ret < 0)
        results.append({"pos": pos, "ret": ret, "correct": correct, "active": pos != 0})

    res_df = pd.DataFrame(results)
    active = res_df[res_df["active"]]
    accuracy = active["correct"].mean() if len(active) > 0 else float("nan")

    contrarian_pnl = (equity_contrarian[-1] - 1) * 100
    bh_pnl = (equity_bh[-1] - 1) * 100

    return {
        "accuracy": accuracy,
        "contrarian_pnl": contrarian_pnl,
        "bh_pnl": bh_pnl,
        "equity_contrarian": equity_contrarian[1:],
        "equity_bh": equity_bh[1:],
    }


def print_report(zone_df: pd.DataFrame, strat: dict) -> None:
    verdict = "Contrarian FNG has edge" if strat["accuracy"] > 0.52 else "No clear edge"
    print()
    print("===================================")
    print("  Backtest 3: Sentiment Correlation")
    print("  Fear & Greed vs BTC 1-day ahead")
    print("===================================")
    header = f"  {'FNG Zone':<18} {'Count':>6}  {'Accuracy':>9}  {'Avg next-day return':>19}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for _, row in zone_df.iterrows():
        acc_str = f"{row['accuracy']*100:.1f}%" if not np.isnan(row["accuracy"]) else "  N/A"
        ret_str = f"{row['avg_ret']*100:+.1f}%" if not np.isnan(row["avg_ret"]) else "  N/A"
        print(f"  {row['zone']:<18} {int(row['count']):>6}  {acc_str:>9}  {ret_str:>19}")
    print()
    print(f"  Contrarian strategy accuracy: {strat['accuracy']*100:.1f}%")
    print(f"  Hold strategy P&L:            {strat['bh_pnl']:.1f}% (BTC buy-hold)")
    print(f"  Contrarian P&L:               {strat['contrarian_pnl']:.1f}%")
    print()
    print(f"  Verdict: {verdict}")
    print("===================================")


def make_chart(zone_df: pd.DataFrame, strat: dict, df: pd.DataFrame, out_path: Path) -> None:
    print("[CHART] Generating chart…")
    fig = plt.figure(figsize=(14, 8), facecolor=BG)
    gs = gridspec.GridSpec(2, 1, figure=fig, hspace=0.45)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    for ax in (ax1, ax2):
        ax.set_facecolor(SURFACE)
        ax.tick_params(colors=TEXT)
        ax.xaxis.label.set_color(TEXT)
        ax.yaxis.label.set_color(TEXT)
        ax.title.set_color(TEXT)
        for spine in ax.spines.values():
            spine.set_edgecolor(GRID)
        ax.grid(color=GRID, linestyle="--", linewidth=0.5, alpha=0.7)

    # ── Subplot 1: Zone accuracy bar ──────────────────────────────────────────
    colors = [ACCENT2, "#f0883e", YELLOW, "#56d364", GREEN]
    zones_list = zone_df["zone"].tolist()
    accs = (zone_df["accuracy"] * 100).tolist()
    counts = zone_df["count"].tolist()

    bars = ax1.bar(zones_list, accs, color=colors, alpha=0.85, edgecolor=GRID, linewidth=0.8)
    ax1.axhline(50, color=TEXT, linestyle="--", linewidth=1, alpha=0.6, label="50% baseline")
    for bar, count, acc in zip(bars, counts, accs):
        if not np.isnan(acc):
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"n={count}",
                ha="center", va="bottom", fontsize=8, color=TEXT,
            )
    ax1.set_title("FNG Zone → Next-Day Up Accuracy", fontsize=12, pad=10)
    ax1.set_ylabel("Accuracy (%)", fontsize=10)
    ax1.set_ylim(35, 70)
    ax1.legend(facecolor=SURFACE, edgecolor=GRID, labelcolor=TEXT, fontsize=8)

    # ── Subplot 2: Cumulative P&L ─────────────────────────────────────────────
    dates = df["date"].values[: len(strat["equity_contrarian"])]
    ax2.plot(dates, np.array(strat["equity_bh"]) * 100 - 100,
             color=ACCENT1, linewidth=1.5, label="Buy & Hold BTC")
    ax2.plot(dates, np.array(strat["equity_contrarian"]) * 100 - 100,
             color=GREEN, linewidth=1.5, label="Contrarian FNG (FNG<30 long / FNG>70 short)")
    ax2.axhline(0, color=GRID, linewidth=0.8)
    ax2.set_title("Cumulative P&L Comparison", fontsize=12, pad=10)
    ax2.set_ylabel("Return (%)", fontsize=10)
    ax2.legend(facecolor=SURFACE, edgecolor=GRID, labelcolor=TEXT, fontsize=8)

    fig.suptitle("Backtest 3 — Fear & Greed Sentiment vs BTC Direction", fontsize=14,
                 color=TEXT, y=0.98)

    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"[CHART] Saved → {out_path}")


def main() -> None:
    fng_df = fetch_fng(365)
    btc_df = fetch_btc_daily(365)

    df = build_dataset(fng_df, btc_df)
    zone_df = analyse_zones(df)
    strat = contrarian_strategy(df)

    print_report(zone_df, strat)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"backtest_3_sentiment_{ts}.png"
    make_chart(zone_df, strat, df, out_path)

    print("\n[DONE] Backtest 3 complete.")


if __name__ == "__main__":
    main()
