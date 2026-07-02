#!/usr/bin/env python3
"""
Generate the funding-carry charts into figures/.

    python scripts/funding_charts.py
    python scripts/funding_charts.py --coins BTC ETH SOL DOGE XRP LTC

Produces:
  figures/portfolio_equity.png      — portfolio equity (equal vs inverse-vol)
  figures/idealized_vs_basis.png    — the honesty gap for one coin
  figures/funding_over_time.png     — funding rate per coin over time
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptostat.funding.portfolio import carry_returns_panel  # noqa: E402
from cryptostat.funding import visualize as viz  # noqa: E402

FIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figures")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", nargs="*",
                    default=["BTC", "ETH", "SOL", "DOGE", "XRP", "LTC"])
    ap.add_argument("--limit", type=int, default=1000)
    args = ap.parse_args()
    os.makedirs(FIG, exist_ok=True)

    print("Fetching carry panel...")
    panel = carry_returns_panel(args.coins, limit=args.limit)

    figs = {
        "portfolio_equity.png": lambda p: viz.plot_portfolio_equity(panel=panel, save_path=p),
        "idealized_vs_basis.png": lambda p: viz.plot_idealized_vs_basis("BTC", limit=args.limit, save_path=p),
        "funding_over_time.png": lambda p: viz.plot_funding_over_time(args.coins, limit=args.limit, save_path=p),
    }
    for name, fn in figs.items():
        path = os.path.join(FIG, name)
        fn(path)
        print(f"  wrote {path}")
    print("\nDone. See figures/.")


if __name__ == "__main__":
    main()
