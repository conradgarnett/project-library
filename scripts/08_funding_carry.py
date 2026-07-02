#!/usr/bin/env python3
"""
Funding-rate carry backtest across several coins (OKX perpetual swaps).

    python scripts/08_funding_carry.py
    python scripts/08_funding_carry.py --coins BTC ETH SOL --limit 1095 --flip

Writes results/funding/carry.txt — the annualized delta-neutral carry yield per
coin, both the naive long-basis version and the flip version.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from cryptostat.funding.carry import carry_backtest  # noqa: E402
from cryptostat.funding.data import funding_history  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "funding")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", nargs="*", default=["BTC", "ETH", "SOL", "DOGE", "XRP"])
    ap.add_argument("--limit", type=int, default=1095, help="funding intervals (8h) of history")
    ap.add_argument("--fee-bps", type=float, default=5.0)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = []
    for c in args.coins:
        try:
            h = funding_history(c, limit=args.limit)
        except Exception as e:  # noqa: BLE001
            print(f"  [skip {c}] {type(e).__name__}: {e}")
            continue
        naive = carry_backtest(h, fee_bps=args.fee_bps, flip=False)
        flip = carry_backtest(h, fee_bps=args.fee_bps, flip=True)
        rows.append({
            "coin": c, "intervals": naive.n_intervals,
            "mean_funding_ann": naive.mean_funding_annualized,
            "carry_yield_naive": naive.ann_yield_simple, "sharpe_naive": naive.sharpe,
            "maxdd_naive": naive.max_drawdown,
            "carry_yield_flip": flip.ann_yield_simple, "sharpe_flip": flip.sharpe,
        })
        print(f"  {c}: funding {naive.mean_funding_annualized:+.2%}/yr | "
              f"naive carry {naive.ann_yield_simple:+.2%} (Sharpe {naive.sharpe:.1f}) | "
              f"flip {flip.ann_yield_simple:+.2%}")

    df = pd.DataFrame(rows).set_index("coin")
    with open(os.path.join(OUT, "carry.txt"), "w") as f:
        f.write("FUNDING-RATE CARRY (OKX perpetual swaps)\n" + "=" * 60 + "\n")
        f.write(f"Generated : {now}\n")
        f.write(f"History   : up to {args.limit} × 8h funding settlements\n")
        f.write(f"Fee       : {args.fee_bps:.0f} bps (setup / per side-flip)\n\n")
        with pd.option_context("display.float_format", lambda v: f"{v:.4f}"):
            f.write(df.to_string())
        f.write("\n\nSTRATEGY\n")
        f.write("  Delta-neutral: long spot + short perp collects funding when it is\n")
        f.write("  positive (longs pay shorts). 'naive' always holds that side (and pays\n")
        f.write("  when funding turns negative); 'flip' switches sides to always collect.\n\n")
        f.write("HONEST CAVEATS\n")
        f.write("  * Assumes a perfect spot/perp hedge, so the high Sharpe reflects an\n")
        f.write("    idealized return stream (steady funding drip, ~zero price variance).\n")
        f.write("    It EXCLUDES the real risks: exchange/counterparty failure (FTX),\n")
        f.write("    perp-leg liquidation on sharp moves, and spot-perp basis drift.\n")
        f.write("  * Yields track the funding regime: rich in bull markets, thin or\n")
        f.write("    negative in calm/bearish ones (see mean_funding_ann per coin).\n")
    print(f"\nWrote → {os.path.join(OUT, 'carry.txt')}")


if __name__ == "__main__":
    main()
