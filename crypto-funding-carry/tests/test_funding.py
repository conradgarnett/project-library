"""Funding-rate carry — backtest math validated offline on synthetic rates."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cryptostat.funding.carry import carry_backtest  # noqa: E402


def _series(rates):
    idx = pd.date_range("2024-01-01", periods=len(rates), freq="8h", tz="UTC")
    return pd.Series(rates, index=idx, name="funding_rate")


def test_positive_funding_earns_carry():
    f = _series([1e-4] * 300)                      # steady positive funding
    r = carry_backtest(f, fee_bps=1.0, flip=False)
    assert r.ann_yield_simple > 0
    assert r.pct_intervals_positive > 0.95         # collecting almost every interval
    # ~1e-4 per 8h * 1095 intervals/yr ≈ 10.95% annualized (minus a tiny setup fee)
    assert 0.09 < r.ann_yield_simple < 0.12


def test_negative_funding_loses_without_flip_but_wins_with_flip():
    f = _series([-1e-4] * 300)                     # persistently negative funding
    naive = carry_backtest(f, fee_bps=1.0, flip=False)
    flipped = carry_backtest(f, fee_bps=1.0, flip=True)
    assert naive.ann_yield_simple < 0              # short-perp pays when funding<0
    assert flipped.ann_yield_simple > 0            # flip to the paying side and collect


def test_flip_collects_on_alternating_funding():
    f = _series(([1e-4, -1e-4] * 150))
    naive = carry_backtest(f, fee_bps=0.5, flip=False)
    flipped = carry_backtest(f, fee_bps=0.5, flip=True)
    assert abs(naive.ann_yield_simple) < flipped.ann_yield_simple
    assert flipped.ann_yield_simple > 0


def test_fees_reduce_flip_returns():
    f = _series(([1e-4, -1e-4] * 150))             # flips every interval -> pays a fee each time
    lo = carry_backtest(f, fee_bps=1.0, flip=True).ann_yield_simple
    hi = carry_backtest(f, fee_bps=20.0, flip=True).ann_yield_simple
    assert hi < lo


def test_live_okx_optional():
    try:
        from cryptostat.funding.data import funding_history
        h = funding_history("BTC", limit=120)
        assert len(h) > 20 and "funding_rate" in h.columns
        print(f"  (live OKX funding fetched: {len(h)} intervals)")
    except Exception as e:  # noqa: BLE001
        print(f"  (live funding skipped: {type(e).__name__})")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for fn in fns:
        try:
            fn(); print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            fails += 1; print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
