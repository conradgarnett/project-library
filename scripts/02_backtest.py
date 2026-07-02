#!/usr/bin/env python3
"""
Walk-forward backtest comparing every allocation method out-of-sample.

    python scripts/02_backtest.py
    python scripts/02_backtest.py --csv my_strategy_returns.csv --lookback 120

Writes results/allocation.txt.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from portlib.backtest import compare_methods  # noqa: E402
from portlib.data import load_returns_csv, returns_panel  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None)
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--lookback", type=int, default=120)
    ap.add_argument("--rebalance", type=int, default=7)
    ap.add_argument("--cost-bps", type=float, default=5.0)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    rets = load_returns_csv(args.csv) if args.csv else returns_panel(days=args.days)
    res = compare_methods(rets, lookback=args.lookback, rebalance=args.rebalance,
                          cost_bps=args.cost_bps)
    table = res["table"]
    cols = ["ann_return", "ann_vol", "sharpe", "max_drawdown", "var_95", "cvar_95"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with pd.option_context("display.float_format", lambda v: f"{v:.4f}"):
        body = table[cols].to_string()
    print(body)

    with open(os.path.join(OUT, "allocation.txt"), "w") as f:
        f.write("MULTI-STRATEGY / MULTI-ASSET ALLOCATION — WALK-FORWARD\n" + "=" * 64 + "\n")
        f.write(f"Generated : {now}\n")
        f.write(f"Universe  : {', '.join(rets.columns)}\n")
        f.write(f"Rows      : {len(rets)} | lookback {args.lookback} | "
                f"rebalance {args.rebalance} | cost {args.cost_bps:.0f} bps\n\n")
        f.write("Out-of-sample performance by allocation method (best Sharpe first):\n\n")
        f.write(body + "\n\n")
        f.write("NOTES\n")
        f.write("  * Every method is walk-forward: weights are estimated on a trailing\n")
        f.write("    window and traded only on the next unseen window (no look-ahead).\n")
        f.write("  * Directional crypto assets are highly correlated, so a long-only book\n")
        f.write("    of them is a HARD case — min-variance/HRP mainly cut risk here.\n")
        f.write("  * The allocator shines on UNCORRELATED return streams: feed your own\n")
        f.write("    market-neutral strategy returns (funding carry, stat-arb) via --csv\n")
        f.write("    and the diversification benefit is far larger.\n")

    # chart
    try:
        from portlib.visualize import plot_method_equity
        fig_dir = os.path.join(os.path.dirname(OUT), "figures")
        os.makedirs(fig_dir, exist_ok=True)
        path = os.path.join(fig_dir, "allocation_equity.png")
        plot_method_equity(res["returns"], save_path=path)
        print(f"chart  -> {path}")
    except Exception as e:  # noqa: BLE001
        print(f"(chart skipped: {type(e).__name__})")
    print(f"Wrote -> {os.path.join(OUT, 'allocation.txt')}")


if __name__ == "__main__":
    main()
