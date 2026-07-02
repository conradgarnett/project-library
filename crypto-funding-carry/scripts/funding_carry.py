#!/usr/bin/env python3
"""
Funding-rate carry backtest across several coins (OKX perpetual swaps).

    python scripts/funding_carry.py
    python scripts/funding_carry.py --coins BTC ETH SOL --limit 1095 --flip

Writes results/funding/carry.txt — the annualized delta-neutral carry yield per
coin, comparing the IDEALIZED (funding-only) model against the BASIS-AWARE model
(real perp/spot price legs). The Sharpe gap is the cost of the perfect-hedge
assumption.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from cryptostat.funding.carry import compare_carry  # noqa: E402

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "funding")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--coins", nargs="*", default=["BTC", "ETH", "SOL", "DOGE", "XRP"])
    ap.add_argument("--limit", type=int, default=1000, help="funding intervals (8h) of history")
    ap.add_argument("--fee-bps", type=float, default=5.0)
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    rows = []
    for c in args.coins:
        try:
            r = compare_carry(c, limit=args.limit, fee_bps=args.fee_bps, flip=False)
        except Exception as e:  # noqa: BLE001
            print(f"  [skip {c}] {type(e).__name__}: {e}")
            continue
        ideal, basis = r["idealized"], r["basis"]
        rows.append({
            "coin": c, "intervals": basis.n_intervals,
            "mean_funding_ann": basis.mean_funding_annualized,
            "yield_ideal": ideal.ann_yield_simple, "sharpe_ideal": ideal.sharpe,
            "yield_basis": basis.ann_yield_simple, "sharpe_basis": basis.sharpe,
            "basis_vol_bps": basis.basis_vol_bps, "maxdd_basis": basis.max_drawdown,
        })
        print(f"  {c}: funding {basis.mean_funding_annualized:+.2%}/yr | "
              f"idealized Sharpe {ideal.sharpe:5.1f} -> basis-aware Sharpe {basis.sharpe:5.1f} "
              f"(basis vol {basis.basis_vol_bps:.2f} bps)")

    df = pd.DataFrame(rows).set_index("coin")
    with open(os.path.join(OUT, "carry.txt"), "w") as f:
        f.write("FUNDING-RATE CARRY (OKX perpetual swaps)\n" + "=" * 64 + "\n")
        f.write(f"Generated : {now}\n")
        f.write(f"History   : up to {args.limit} x 8h funding settlements\n")
        f.write(f"Fee       : {args.fee_bps:.0f} bps (setup)\n\n")
        with pd.option_context("display.float_format", lambda v: f"{v:.4f}"):
            f.write(df.to_string())
        f.write("\n\nSTRATEGY\n")
        f.write("  Delta-neutral: long spot + short perp collects funding when it is\n")
        f.write("  positive (longs pay shorts).\n\n")
        f.write("IDEALIZED vs BASIS-AWARE\n")
        f.write("  idealized: return = funding only (assumes a perfect hedge).\n")
        f.write("  basis-aware: return = funding + real price-leg P&L (= -d(perp/spot-1)),\n")
        f.write("  using actual OKX perp & spot prices at each funding time.\n")
        f.write("  The basis LEVEL is tiny (single-digit bps, same venue) but its\n")
        f.write("  interval-to-interval CHANGES are large relative to the minuscule 8h\n")
        f.write("  funding drip, so the honest (basis-aware) Sharpe is much lower than\n")
        f.write("  the idealized one. That gap is the cost of the perfect-hedge assumption.\n\n")
        f.write("STILL NOT MODELED (real risks that would lower this further)\n")
        f.write("  * perp-leg liquidation on sharp moves (margin management)\n")
        f.write("  * exchange / counterparty failure (e.g. FTX)\n")
        f.write("  * cross-venue hedging would add a much larger, noisier basis\n")
    print(f"\nWrote -> {os.path.join(OUT, 'carry.txt')}")


if __name__ == "__main__":
    main()
