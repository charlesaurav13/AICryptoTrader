#!/usr/bin/env python3
"""
Run all CryptoSwarm backtests in sequence.
Usage: python backend/scripts/run_all_backtests.py

Backtests:
  1. Kronos direction accuracy
  2. Technical indicator signals (QuantAgent)
  3. Fear & Greed sentiment correlation
  4. Combined signal agreement analysis
  5. SL/TP optimization grid
  6. Walk-forward Kronos validation

Results saved to: backend/backtest_results/
"""
import subprocess, sys, time
from pathlib import Path

SCRIPTS = [
    ("1", "backtest_1_kronos.py",       "Kronos Direction Accuracy"),
    ("2", "backtest_2_quant.py",         "Technical Indicators (QuantAgent)"),
    ("3", "backtest_3_sentiment.py",     "Sentiment / Fear & Greed"),
    ("4", "backtest_4_combined.py",      "Combined Signal Agreement"),
    ("5", "backtest_5_sltp.py",          "SL/TP Optimization"),
    ("6", "backtest_6_walkforward.py",   "Walk-Forward Validation"),
]

def run_all():
    scripts_dir = Path(__file__).parent
    results_dir = scripts_dir.parent / "backtest_results"
    results_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("  CryptoSwarm Backtest Suite")
    print("=" * 60)

    summary = []
    for num, script, name in SCRIPTS:
        print(f"\n[{num}/6] {name}")
        print("-" * 40)
        t0 = time.time()
        try:
            result = subprocess.run(
                [sys.executable, str(scripts_dir / script)],
                capture_output=False,
                timeout=3600,  # 1h max per backtest
            )
            elapsed = time.time() - t0
            status = "OK" if result.returncode == 0 else "FAILED"
            summary.append((num, name, status, f"{elapsed/60:.1f}m"))
        except subprocess.TimeoutExpired:
            summary.append((num, name, "TIMEOUT", ">60m"))
        except Exception as e:
            summary.append((num, name, f"ERROR: {e}", "-"))

    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for num, name, status, elapsed in summary:
        print(f"  [{num}] {name:<35} {status}  ({elapsed})")
    print(f"\n  Results saved to: {results_dir}")
    print("=" * 60)

if __name__ == "__main__":
    run_all()
