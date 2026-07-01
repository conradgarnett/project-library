#!/usr/bin/env python3
"""
Step 1 — download and cache a universe of daily crypto prices.

    python scripts/01_fetch_universe.py            # default universe, 2y daily
    python scripts/01_fetch_universe.py --days 1095 --granularity 1d
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptostat.data import DEFAULT_UNIVERSE, price_panel  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="*", default=DEFAULT_UNIVERSE)
    ap.add_argument("--exchange", default="coinbase")
    ap.add_argument("--granularity", default="1d")
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--refresh", action="store_true", help="ignore cache and re-download")
    args = ap.parse_args()

    print(f"Fetching {len(args.symbols)} symbols from {args.exchange} "
          f"({args.granularity}, {args.days}d)...")
    panel = price_panel(args.symbols, args.exchange, args.granularity, args.days,
                        force_refresh=args.refresh)
    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "data", "panel.csv")
    panel.to_csv(out)
    print(f"\nPanel: {panel.shape[0]} rows × {panel.shape[1]} symbols")
    print(f"Date range: {panel.index.min().date()} → {panel.index.max().date()}")
    print(f"Saved → {out}")


if __name__ == "__main__":
    main()
