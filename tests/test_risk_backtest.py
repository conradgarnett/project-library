"""Risk metrics and the walk-forward backtest."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from portlib.backtest import compare_methods, walk_forward  # noqa: E402
from portlib.risk import (  # noqa: E402
    conditional_var,
    historical_var,
    max_drawdown,
    parametric_var,
)


def _panel(n=800, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2023-01-01", periods=n, freq="D", tz="UTC")
    # uncorrelated assets, different vols -> diversification should help
    vols = [0.01, 0.015, 0.02, 0.025]
    return pd.DataFrame(rng.standard_normal((n, 4)) * vols,
                        columns=list("ABCD"), index=idx)


def test_var_and_cvar():
    rng = np.random.default_rng(0)
    r = rng.standard_normal(100000) * 0.02
    # ~Gaussian: historical and parametric 95% VaR should be close
    assert abs(historical_var(r, 0.95) - parametric_var(r, 0.95)) < 0.002
    assert conditional_var(r, 0.95) >= historical_var(r, 0.95)   # ES deeper in the tail


def test_max_drawdown_signs():
    up = pd.Series([0.01] * 50)
    assert abs(max_drawdown(up)) < 1e-9                # monotonic up -> ~0
    down = pd.Series([-0.02] * 20)
    assert max_drawdown(down) < -0.2                   # sustained losses -> big dd


def test_walk_forward_no_lookahead():
    df = _panel()
    port, weights = walk_forward(df, method="risk_parity", lookback=100, rebalance=10)
    # OOS series only exists after the first lookback window
    assert len(port) <= len(df) - 100
    assert len(port) >= len(df) - 100 - 10
    assert np.allclose(weights.sum(axis=1).values, 1.0, atol=1e-6)


def test_diversification_reduces_vol_out_of_sample():
    df = _panel()
    port, _ = walk_forward(df, method="min_variance", lookback=100, rebalance=10, cost_bps=0.0)
    # portfolio vol should be below the average single-asset vol
    assert port.std() < df.std().mean()


def test_compare_methods_table():
    res = compare_methods(_panel(), lookback=100, rebalance=20, cost_bps=0.0)
    assert set(res["table"].index).issubset(set(
        ["equal", "inverse_vol", "min_variance", "max_sharpe", "risk_parity", "hrp"]))
    assert "sharpe" in res["table"].columns and len(res["table"]) >= 4


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
