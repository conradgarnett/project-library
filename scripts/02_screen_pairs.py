#!/usr/bin/env python3
"""
Step 2 — screen the universe for cointegrated, tradeable pairs.

    python scripts/02_screen_pairs.py                 # uses data/panel.csv
    python scripts/02_screen_pairs.py --min-corr 0.6

Writes a ranked table to data/pairs.csv. Candidate pairs (cointegrated with a
tradeable half-life) are listed first.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from cryptostat.data import DEFAULT_UNIVERSE, price_panel  # noqa: E402
from cryptostat.pairs import screen_pairs  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default=os.path.join(DATA, "panel.csv"))
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--alpha", type=float, default=0.05)
    ap.add_argument("--min-corr", type=float, default=0.5)
    args = ap.parse_args()

    if os.path.exists(args.panel):
        panel = pd.read_csv(args.panel, index_col=0, parse_dates=True)
    else:
        print("panel.csv not found — fetching the default universe first...")
        panel = price_panel(DEFAULT_UNIVERSE, days=args.days)

    table = screen_pairs(panel, alpha=args.alpha, min_corr=args.min_corr)
    out = os.path.join(DATA, "pairs.csv")
    table.to_csv(out, index=False)

    n_cand = int(table["candidate"].sum()) if len(table) else 0
    print(f"\nTested {len(table)} pairs — {n_cand} candidate(s) "
          f"(cointegrated @ {args.alpha:.0%} + tradeable half-life)\n")
    cols = ["dependent", "independent", "corr", "eg_stat", "eg_pvalue",
            "beta", "half_life", "candidate"]
    with pd.option_context("display.float_format", lambda v: f"{v:.4f}"):
        print(table[cols].head(15).to_string(index=False))
    print(f"\nSaved ranked table → {out}")


if __name__ == "__main__":
    main()
