"""Backtest engine + signals + metrics on synthetic pairs (offline)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cryptostat.backtest import backtest_pair  # noqa: E402
from cryptostat.metrics import max_drawdown, performance_summary, sharpe  # noqa: E402
from cryptostat.signals import zscore_signal  # noqa: E402


def _mean_reverting_pair(n=3000, seed=0, beta=1.5, amp=6.0, theta=0.05):
    """Construct A, B whose spread A - beta*B is a strong OU (should be tradeable)."""
    rng = np.random.default_rng(seed)
    b = np.cumsum(rng.standard_normal(n)) * 0.5 + 100      # leg B random walk
    spread = np.zeros(n)
    for t in range(1, n):
        spread[t] = spread[t - 1] - theta * spread[t - 1] + rng.standard_normal() * amp * np.sqrt(theta)
    a = beta * b + spread
    idx = pd.date_range("2022-01-01", periods=n, freq="D", tz="UTC")
    return pd.Series(a, idx), pd.Series(b, idx)


def test_signal_positions_are_valid():
    z = np.array([0, -3, -1, 0, 3, 1, 0, -3, 0], dtype=float)
    pos = zscore_signal(z, entry=2.0, exit=0.5)
    assert set(np.unique(pos)).issubset({-1.0, 0.0, 1.0})
    assert pos[1] == 1.0          # entered long when z <= -entry
    assert pos[4] == -1.0         # flipped short when z >= +entry


def test_backtest_profits_on_mean_reverting_spread():
    a, b = _mean_reverting_pair()
    res = backtest_pair(a, b, z_window=30, entry=2.0, exit=0.5, cost_bps=1.0)
    perf = performance_summary(res.returns)
    assert res.n_trades > 5
    assert perf.sharpe > 0.5      # a real OU spread should be tradeable
    assert abs(res.beta - 1.5) < 0.1


def test_no_lookahead_flat_when_never_triggered():
    # A spread that never crosses the entry band should never take a position.
    a, b = _mean_reverting_pair(amp=0.2)
    res = backtest_pair(a, b, z_window=30, entry=50.0, exit=0.5)
    assert res.n_trades == 0
    assert (res.returns.abs() < 1e-12).all()


def test_costs_reduce_returns():
    a, b = _mean_reverting_pair()
    lo = performance_summary(backtest_pair(a, b, cost_bps=1.0).returns).ann_return
    hi = performance_summary(backtest_pair(a, b, cost_bps=100.0).returns).ann_return
    assert hi < lo                # higher costs => lower return


def test_metrics_on_known_series():
    r = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
    assert sharpe(r) != 0.0
    mdd, _, _ = max_drawdown(r)
    assert mdd <= 0.0


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
