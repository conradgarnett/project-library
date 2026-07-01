"""Walk-forward harness: no leakage, and it works on a genuinely tradeable spread."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cryptostat.walkforward import walk_forward  # noqa: E402


def _mean_reverting_pair(n=2000, seed=0, beta=1.5, amp=6.0, theta=0.05):
    rng = np.random.default_rng(seed)
    b = np.cumsum(rng.standard_normal(n)) * 0.5 + 100
    spread = np.zeros(n)
    for t in range(1, n):
        spread[t] = spread[t - 1] - theta * spread[t - 1] + rng.standard_normal() * amp * np.sqrt(theta)
    a = beta * b + spread
    idx = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    return pd.Series(a, idx), pd.Series(b, idx)


def test_oos_length_and_coverage():
    a, b = _mean_reverting_pair()
    wf = walk_forward(a, b, train=180, test=30)
    # OOS series starts after the first training window and covers whole folds.
    assert len(wf.oos_returns) <= len(a) - 180
    assert len(wf.oos_returns) >= (len(a) - 180) - 30
    assert len(wf.folds) > 5


def test_genuine_spread_is_tradeable_out_of_sample():
    a, b = _mean_reverting_pair(amp=8.0)
    wf = walk_forward(a, b, train=200, test=40, cost_bps=1.0)
    assert wf.oos_sharpe > 0.3         # a real OU spread should survive OOS


def test_no_leakage_flat_when_untriggered():
    # Spread so tight the entry band is never crossed => no OOS trades, zero P&L.
    a, b = _mean_reverting_pair(amp=0.2)
    wf = walk_forward(a, b, train=180, test=30, entry=50.0)
    assert wf.folds["n_trades"].sum() == 0
    assert (wf.oos_returns.abs() < 1e-12).all()


def test_recheck_coint_stands_down_on_broken_pair():
    # Two independent random walks: not cointegrated -> harness should stand down.
    rng = np.random.default_rng(7)
    n = 1200
    a = pd.Series(np.cumsum(rng.standard_normal(n)) + 100)
    b = pd.Series(np.cumsum(rng.standard_normal(n)) + 100)
    wf = walk_forward(a, b, train=250, test=40, recheck_coint=True)
    assert wf.folds["stood_down"].any()


def test_anchored_mode_runs():
    a, b = _mean_reverting_pair()
    wf = walk_forward(a, b, train=180, test=30, anchored=True)
    assert len(wf.folds) > 5


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
