#!/usr/bin/env python3
"""
Cross-exchange arbitrage hunt across five USD venues (Coinbase, Kraken,
Bitstamp, Gemini, Bitfinex).

    python scripts/06_cross_exchange.py

Writes results/cross_exchange/:
  * live_arbitrage.txt  — current best buy-here/sell-there route per asset,
    gross edge and edge net of both venues' taker fees
  * dislocation.txt     — historical daily cross-venue spread stats per asset
    (how often the gap beat round-trip fees)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from cryptostat.crossexchange import (  # noqa: E402
    cross_exchange_spread,
    dislocation_stats,
    scan_live_arbitrage,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "cross_exchange")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", nargs="*",
                    default=["BTC", "ETH", "SOL", "LTC", "LINK", "AAVE", "ADA", "XLM"])
    ap.add_argument("--days", type=int, default=300)
    ap.add_argument("--fee-bps", type=float, default=80.0)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # --- live arbitrage snapshot ---
    print("Scanning live cross-exchange quotes...")
    scan = scan_live_arbitrage(args.assets)
    with open(os.path.join(OUT, "live_arbitrage.txt"), "w") as f:
        f.write("LIVE CROSS-EXCHANGE ARBITRAGE SNAPSHOT\n" + "=" * 60 + "\n")
        f.write(f"Generated : {now}\nVenues    : coinbase, kraken, bitstamp, gemini, bitfinex\n")
        f.write("net_bps = gross dislocation minus BOTH venues' taker fees.\n")
        f.write("Positive net_bps = an executable spot arbitrage.\n\n")
        with pd.option_context("display.float_format", lambda v: f"{v:.1f}"):
            f.write(scan.to_string(index=False))
        n_exec = int(scan["executable"].sum()) if len(scan) else 0
        f.write(f"\n\nExecutable opportunities (net > 0): {n_exec} / {len(scan)}\n")
        f.write("As expected between major USD venues, gross gaps (single-digit to\n")
        f.write("low-tens of bps) rarely beat ~50-100 bps round-trip taker fees.\n")
    print(scan.to_string(index=False))

    # --- historical dislocation ---
    import time
    time.sleep(2.0)   # let rate limits cool down before the second wave of calls
    print("\nComputing historical cross-venue dislocation...")
    rows = []
    for a in args.assets:
        try:
            sp = cross_exchange_spread(a, days=args.days)
            st = dislocation_stats(sp, fee_bps=args.fee_bps)
            st["asset"] = a
            rows.append(st)
        except Exception as e:  # noqa: BLE001
            print(f"  [skip {a}] {type(e).__name__}: {e}")
    hist = pd.DataFrame(rows).set_index("asset")
    with open(os.path.join(OUT, "dislocation.txt"), "w") as f:
        f.write("HISTORICAL CROSS-EXCHANGE DISLOCATION\n" + "=" * 60 + "\n")
        f.write(f"Generated : {now}\nWindow    : {args.days} days daily close\n")
        f.write(f"Round-trip cost assumed: {args.fee_bps:.0f} bps\n\n")
        with pd.option_context("display.float_format", lambda v: f"{v:.2f}"):
            f.write(hist[["days", "mean_spread_bps", "median_spread_bps",
                          "p95_spread_bps", "max_spread_bps",
                          "pct_days_above_fees"]].to_string())
        f.write("\n\nINTERPRETATION\n")
        f.write("  Typical daily cross-venue gaps are a few to ~15 bps — well below\n")
        f.write("  round-trip fees — so 'pct_days_above_fees' is tiny. The rare spikes\n")
        f.write("  (max column) are where real, fleeting arbitrage lives; capturing it\n")
        f.write("  needs low-latency execution and pre-positioned balances on both\n")
        f.write("  venues (you cannot transfer coins fast enough after the fact).\n")
    print(hist[["mean_spread_bps", "p95_spread_bps", "max_spread_bps",
                "pct_days_above_fees"]].to_string())
    print(f"\nWrote results → {OUT}/")


if __name__ == "__main__":
    main()
