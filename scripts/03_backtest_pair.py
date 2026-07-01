#!/usr/bin/env python3
"""
Step 3 — backtest one pair with the baseline z-score strategy.

    python scripts/03_backtest_pair.py --a BCH-USD --b LTC-USD
    python scripts/03_backtest_pair.py --a ETH-USD --b BTC-USD --entry 2.5 --exit 0.25

Prints a performance tearsheet and (if matplotlib is available) saves an equity
+ spread chart to figures/.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from cryptostat.backtest import backtest_pair  # noqa: E402
from cryptostat.data import fetch_ohlcv  # noqa: E402
from cryptostat.metrics import equity_curve, performance_summary  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="leg A symbol, e.g. BCH-USD")
    ap.add_argument("--b", required=True, help="leg B symbol, e.g. LTC-USD")
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--z-window", type=int, default=30)
    ap.add_argument("--entry", type=float, default=2.0)
    ap.add_argument("--exit", type=float, default=0.5)
    ap.add_argument("--stop", type=float, default=None)
    ap.add_argument("--cost-bps", type=float, default=10.0)
    args = ap.parse_args()

    a = fetch_ohlcv(args.a, days=args.days)["close"]
    b = fetch_ohlcv(args.b, days=args.days)["close"]
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()

    res = backtest_pair(joined["a"], joined["b"], z_window=args.z_window,
                        entry=args.entry, exit=args.exit, stop=args.stop,
                        cost_bps=args.cost_bps)
    perf = performance_summary(res.returns)

    print(f"\n=== {args.a} vs {args.b} — baseline z-score strategy ===")
    print(f"  hedge ratio β   {res.beta:.4f}")
    print(f"  trades          {res.n_trades}")
    print(f"  ann. return     {perf.ann_return:.2%}")
    print(f"  ann. vol        {perf.ann_vol:.2%}")
    print(f"  Sharpe          {perf.sharpe:.2f}")
    print(f"  Sortino         {perf.sortino:.2f}")
    print(f"  Calmar          {perf.calmar:.2f}")
    print(f"  max drawdown    {perf.max_drawdown:.2%}")
    print(f"  hit rate        {perf.hit_rate:.2%}")

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
        equity_curve(res.returns).plot(ax=ax1, color="#1f77b4", lw=1.6)
        ax1.set_title(f"{args.a} / {args.b} — strategy equity (Sharpe {perf.sharpe:.2f})")
        ax1.set_ylabel("equity (×)"); ax1.grid(alpha=0.3)
        res.zscore.plot(ax=ax2, color="#333", lw=1)
        for lv, c in [(args.entry, "r"), (-args.entry, "r"), (args.exit, "g"), (-args.exit, "g")]:
            ax2.axhline(lv, color=c, ls="--", lw=0.8, alpha=0.6)
        ax2.set_title("spread z-score"); ax2.set_ylabel("z"); ax2.grid(alpha=0.3)
        os.makedirs(os.path.join(ROOT, "figures"), exist_ok=True)
        out = os.path.join(ROOT, "figures", f"backtest_{args.a}_{args.b}.png")
        fig.tight_layout(); fig.savefig(out, dpi=130)
        print(f"\n  chart → {out}")
    except Exception as e:  # noqa: BLE001
        print(f"\n  (plot skipped: {type(e).__name__})")


if __name__ == "__main__":
    main()
