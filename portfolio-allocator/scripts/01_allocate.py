#!/usr/bin/env python3
"""
Compute portfolio weights across a universe with every method, plus a risk
report and risk contributions for one chosen method.

    python scripts/01_allocate.py
    python scripts/01_allocate.py --method hrp --lookback 180

Uses free daily crypto returns by default; pass --csv to allocate across your own
strategy return streams instead.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from portlib.allocate import METHODS, allocate  # noqa: E402
from portlib.covariance import cov_estimate  # noqa: E402
from portlib.data import load_returns_csv, returns_panel  # noqa: E402
from portlib.riskparity import risk_contributions  # noqa: E402
from portlib.risk import risk_report  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None, help="returns CSV (else free crypto)")
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--method", default="risk_parity", choices=list(METHODS))
    ap.add_argument("--lookback", type=int, default=180)
    args = ap.parse_args()

    rets = load_returns_csv(args.csv) if args.csv else returns_panel(days=args.days)
    train = rets.tail(args.lookback)
    print(f"Universe: {list(rets.columns)}  ({len(rets)} rows)\n")

    print("Weights by method (estimated on the last %d rows):" % args.lookback)
    w_all = pd.DataFrame({m: allocate(train, method=m) for m in METHODS})
    with pd.option_context("display.float_format", lambda v: f"{v:.3f}"):
        print(w_all.to_string())

    w = allocate(train, method=args.method)
    rc = risk_contributions(w, cov_estimate(train))
    print(f"\n[{args.method}] risk contributions (share of portfolio risk):")
    with pd.option_context("display.float_format", lambda v: f"{v:.3f}"):
        print((rc / rc.sum()).to_string())

    port = (rets * w.reindex(rets.columns).fillna(0)).sum(axis=1)
    print(f"\n[{args.method}] full-sample risk report:")
    for k, v in risk_report(port).as_dict().items():
        print(f"    {k:14s} {v:.4f}")


if __name__ == "__main__":
    main()
