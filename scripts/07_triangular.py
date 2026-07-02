#!/usr/bin/env python3
"""
Cross-venue triangular / cyclic arbitrage scan.

Builds a live conversion-rate graph across five USD exchanges and searches for
profitable loops (USD -> ... -> USD). Reports the best MULTI-venue loop (each leg
on its best exchange) vs the best SINGLE-venue loop, so you can see exactly what
trading across sources adds.

    python scripts/07_triangular.py
    python scripts/07_triangular.py --assets USD BTC ETH SOL LTC XRP --max-len 4

Writes results/triangular.txt.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptostat.crossvenue.arbgraph import scan  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results")


def _fmt_cycle(c):
    if c is None:
        return "  (none found)\n"
    lines = [f"  net {c.net_return * 1e4:+.1f} bps  |  gross {c.gross_return * 1e4:+.1f} bps"
             f"  |  multi-venue={c.multi_venue()}"]
    for frm, to, ex, rate in c.legs:
        lines.append(f"    {frm:>5} -> {to:<5} @ {ex}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets", nargs="*", default=["USD", "BTC", "ETH", "SOL", "LTC"])
    ap.add_argument("--quotes", nargs="*", default=["USD", "BTC"])
    ap.add_argument("--max-len", type=int, default=4)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    print("Building cross-venue rate graph (live)...")
    r = scan(assets=tuple(args.assets), base="USD", max_len=args.max_len,
             quotes=tuple(args.quotes))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    best_tri = next((c for c in r["all_multi"] if len(c.legs) >= 3), None)
    n_prof = sum(1 for c in r["all_multi"] if c.net_return > 0)

    lines = []
    lines.append("CROSS-VENUE TRIANGULAR / CYCLIC ARBITRAGE\n" + "=" * 60)
    lines.append(f"Generated : {now}")
    lines.append(f"Assets    : {', '.join(args.assets)}")
    lines.append(f"Venues    : coinbase, kraken, bitstamp, gemini, bitfinex")
    lines.append(f"Edges     : {len(r['edges'])} live conversion rates\n")
    lines.append("BEST MULTI-VENUE LOOP (each leg on its best exchange)")
    lines.append(_fmt_cycle(r["best_multi"]))
    lines.append("BEST 3+ LEG TRIANGLE (multi-venue)")
    lines.append(_fmt_cycle(best_tri))
    lines.append("BEST SINGLE-VENUE LOOP (all legs one exchange)")
    lines.append(_fmt_cycle(r["best_single"]))
    lines.append("PER-EXCHANGE BEST NET (bps)")
    lines.append("  " + "  ".join(f"{k}:{v.net_return*1e4:+.0f}" for k, v in r["per_exchange"].items()))
    lines.append(f"\nProfitable loops after fees (net>0): {n_prof} / {len(r['all_multi'])}\n")
    lines.append("INTERPRETATION")
    lines.append("  Using multiple sources DOES widen the best available loop (compare the")
    lines.append("  multi-venue vs single-venue net above) and often turns up a positive")
    lines.append("  GROSS edge. But each leg pays a taker fee, so ~3 legs cost ~1-2% round")
    lines.append("  trip — and cross-venue loops also require moving assets between")
    lines.append("  exchanges, which is slow: by the time coins settle, the prices have")
    lines.append("  moved. So these are MEASURED opportunities, not executable free money")
    lines.append("  unless you pre-position inventory on every venue and act in milliseconds.")

    text = "\n".join(lines)
    with open(os.path.join(OUT, "triangular.txt"), "w") as f:
        f.write(text + "\n")
    print(text)
    print(f"\nWrote → {os.path.join(OUT, 'triangular.txt')}")


if __name__ == "__main__":
    main()
