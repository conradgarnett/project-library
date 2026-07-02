#!/usr/bin/env python3
"""
Step 4 — walk-forward (out-of-sample) validation of a pair.

Re-estimates the hedge ratio and z-score stats on a rolling training window and
trades only the next unseen window. Reports the honest out-of-sample Sharpe next
to the optimistic full-sample number — the gap is your overfitting tax.

    python scripts/04_walk_forward.py --a BCH-USD --b LTC-USD
    python scripts/04_walk_forward.py --a MATIC-USD --b ADA-USD --train 200 --test 40 --recheck-coint
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from cryptostat.common.data import fetch_ohlcv  # noqa: E402
from cryptostat.statarb.walkforward import walk_forward  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--train", type=int, default=180)
    ap.add_argument("--test", type=int, default=30)
    ap.add_argument("--entry", type=float, default=2.0)
    ap.add_argument("--exit", type=float, default=0.5)
    ap.add_argument("--cost-bps", type=float, default=10.0)
    ap.add_argument("--anchored", action="store_true")
    ap.add_argument("--recheck-coint", action="store_true")
    args = ap.parse_args()

    a = fetch_ohlcv(args.a, days=args.days)["close"]
    b = fetch_ohlcv(args.b, days=args.days)["close"]
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()

    wf = walk_forward(joined["a"], joined["b"], train=args.train, test=args.test,
                      entry=args.entry, exit=args.exit, cost_bps=args.cost_bps,
                      anchored=args.anchored, recheck_coint=args.recheck_coint)

    print(f"\n=== {args.a} vs {args.b} — walk-forward validation ===")
    print(wf.summary())
    print("\nper-fold out-of-sample Sharpe:")
    with pd.option_context("display.float_format", lambda v: f"{v:.3f}"):
        show = wf.folds[["test_start", "test_end", "beta", "train_sharpe",
                         "test_sharpe", "n_trades", "stood_down"]].copy()
        show["test_start"] = pd.to_datetime(show["test_start"]).dt.date
        show["test_end"] = pd.to_datetime(show["test_end"]).dt.date
        print(show.to_string(index=False))


if __name__ == "__main__":
    main()
