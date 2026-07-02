#!/usr/bin/env python3
"""
Plot the Markowitz efficient frontier with the individual assets and every
allocation method marked on the risk/return plane.

    python scripts/03_frontier.py
    python scripts/03_frontier.py --csv my_returns.csv --lookback 250

Writes figures/efficient_frontier.png.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from portlib.data import load_returns_csv, returns_panel  # noqa: E402
from portlib.visualize import plot_efficient_frontier  # noqa: E402

FIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figures")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None)
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--lookback", type=int, default=730, help="rows used to estimate mean/cov")
    ap.add_argument("--rf", type=float, default=0.0, help="per-period risk-free rate")
    ap.add_argument("--ppy", type=int, default=365, help="periods per year (365 daily crypto)")
    args = ap.parse_args()
    os.makedirs(FIG, exist_ok=True)

    rets = load_returns_csv(args.csv) if args.csv else returns_panel(days=args.days)
    rets = rets.tail(args.lookback)
    print(f"Universe: {list(rets.columns)} ({len(rets)} rows)")
    path = os.path.join(FIG, "efficient_frontier.png")
    plot_efficient_frontier(rets, periods_per_year=args.ppy, rf=args.rf, save_path=path)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
