#!/usr/bin/env python3
"""
Cross-venue triangular / cyclic arbitrage scanner.

Builds a live conversion-rate graph across five free USD exchanges (Coinbase,
Kraken, Bitstamp, Gemini, Bitfinex) and searches for profitable loops
USD -> ... -> USD, each leg on its best venue — net of taker fees.

    python arb_scan.py
    python arb_scan.py --assets USD BTC ETH SOL LTC --max-len 4

This is the no-arbitrage complement to the pricing library: options pricing
assumes no free lunch (put-call parity, etc.); this measures how close real
cross-venue markets actually are to that assumption.
"""

from __future__ import annotations

import argparse

from optlib.arbgraph import scan


def _fmt(c):
    if c is None:
        return "  (none)"
    legs = "  ".join(f"{frm}->{to}@{ex}" for frm, to, ex, _ in c.legs)
    return (f"  net {c.net_return*1e4:+.1f} bps | gross {c.gross_return*1e4:+.1f} bps"
            f" | multi-venue={c.multi_venue()}\n    {legs}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", nargs="*", default=["USD", "BTC", "ETH", "SOL", "LTC"])
    ap.add_argument("--quotes", nargs="*", default=["USD", "BTC"])
    ap.add_argument("--max-len", type=int, default=4)
    args = ap.parse_args()

    print("Building live cross-venue rate graph...")
    r = scan(assets=tuple(args.assets), base="USD", max_len=args.max_len,
             quotes=tuple(args.quotes))
    n_prof = sum(1 for c in r["all_multi"] if c.net_return > 0)
    print(f"\nEdges: {len(r['edges'])}")
    print("BEST MULTI-VENUE LOOP:\n" + _fmt(r["best_multi"]))
    print("BEST SINGLE-VENUE LOOP:\n" + _fmt(r["best_single"]))
    print(f"\nProfitable loops after fees: {n_prof} / {len(r['all_multi'])}")


if __name__ == "__main__":
    main()
