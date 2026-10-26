#!/usr/bin/env python3
"""
Step 8 — ML / neural-network pairs trading, judged out-of-sample.

Trains a model on each walk-forward *training* window and trades only the next
unseen window, exactly like ``04_walk_forward.py`` — but the position comes from
a learned model instead of a fixed z-score band. Prints the ML strategy next to
the z-score baseline so you can see the honest OOS gap (and whether the model is
worth its complexity).

    python scripts/08_ml_pairs.py --a LINK-USD --b LTC-USD
    python scripts/08_ml_pairs.py --a DOT-USD  --b FIL-USD --kind gbm --horizon 5
    python scripts/08_ml_pairs.py --a LINK-USD --b LTC-USD --both   # base vs ridge vs gbm vs lstm

Overfitting defences are on by default: each fold trains a 3-seed ensemble and
trades only when the frozen z-score agrees with the model's direction
(--ensemble / --z-gate to change, --z-gate 0 to disable, --tune to also pick the
conviction gate per fold on a validation tail of the training window).

Neural nets are data-hungry: on ~2y of *daily* bars the simple z-score is a
strong baseline and hard to beat. The value here is the honest, leakage-free
framework — swap in more data (higher frequency), richer features, or continuous
sizing and re-run. The judge (OOS Sharpe) never moves.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from cryptostat.common.data import fetch_ohlcv  # noqa: E402
from cryptostat.statarb.walkforward import walk_forward  # noqa: E402
from cryptostat.statarb.ml import walk_forward_ml  # noqa: E402


def _line(name, wf):
    p = wf.performance()
    print(f"  {name:16s} OOS Sharpe {wf.oos_sharpe:6.2f}  |  in-sample {wf.insample_sharpe:6.2f}"
          f"  |  ann.ret {p.ann_return:7.2%}  maxDD {p.max_drawdown:7.2%}  "
          f"hit {p.hit_rate:5.1%}  ({len(wf.folds)} folds)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--days", type=int, default=900)
    ap.add_argument("--granularity", default="1d")
    ap.add_argument("--train", type=int, default=250)
    ap.add_argument("--test", type=int, default=30)
    ap.add_argument("--kind", choices=["lstm", "gbm", "ridge"], default="lstm")
    ap.add_argument("--horizon", type=int, default=5, help="reversion horizon the label looks ahead")
    ap.add_argument("--entry-sigma", type=float, default=0.5, help="conviction gate, in prediction-σ")
    ap.add_argument("--ensemble", type=int, default=3, help="models per fold (seed ensemble)")
    ap.add_argument("--z-gate", type=float, default=1.0,
                    help="trade only when the frozen z-score agrees (0 disables)")
    ap.add_argument("--tune", action="store_true",
                    help="pick entry-sigma per fold on a validation tail of train")
    ap.add_argument("--cost-bps", type=float, default=10.0)
    ap.add_argument("--recheck-coint", action="store_true")
    ap.add_argument("--both", action="store_true", help="run baseline + ridge + gbm + lstm")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    a = fetch_ohlcv(args.a, granularity=args.granularity, days=args.days)["close"]
    b = fetch_ohlcv(args.b, granularity=args.granularity, days=args.days)["close"]
    joined = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
    ppy = {"1d": 365, "1h": 24 * 365, "6h": 4 * 365}.get(args.granularity, 365)

    print(f"\n=== {args.a} vs {args.b} — ML pairs trading, walk-forward "
          f"({args.granularity}, {len(joined)} bars) ===")

    base = walk_forward(joined["a"], joined["b"], train=args.train, test=args.test,
                        cost_bps=args.cost_bps, recheck_coint=args.recheck_coint,
                        periods_per_year=ppy)
    _line("z-score (base)", base)

    kinds = ["ridge", "gbm", "lstm"] if args.both else [args.kind]
    for kind in kinds:
        wf = walk_forward_ml(joined["a"], joined["b"], train=args.train, test=args.test,
                             kind=kind, horizon=args.horizon, entry_sigma=args.entry_sigma,
                             n_ensemble=args.ensemble,
                             z_gate=args.z_gate if args.z_gate > 0 else None,
                             tune_entry=args.tune,
                             cost_bps=args.cost_bps, recheck_coint=args.recheck_coint,
                             periods_per_year=ppy, seed=args.seed)
        _line(f"ML: {kind}", wf)

    print("\nReminder: the honest number is OOS Sharpe. A big in-sample→OOS gap "
          "means the model overfit — prefer the simpler signal when they tie.")


if __name__ == "__main__":
    main()
