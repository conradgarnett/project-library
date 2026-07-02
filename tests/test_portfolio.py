"""Carry portfolio — diversification math validated offline on synthetic streams."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from cryptostat.funding.portfolio import carry_portfolio  # noqa: E402


def _panel(n=600, vols=(1e-4, 1e-4, 1e-4), mean=5e-5, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="8h", tz="UTC")
    cols = {}
    for i, v in enumerate(vols):
        cols[f"C{i}"] = mean + rng.standard_normal(n) * v      # independent streams
    return pd.DataFrame(cols, index=idx)


def test_diversification_raises_sharpe():
    panel = _panel()
    r = carry_portfolio(panel, scheme="equal")
    assert r.diversification_ratio > 1.3          # ~sqrt(3) for 3 independent streams
    assert r.sharpe > r.avg_standalone_sharpe     # the whole point


def test_weights_sum_to_one():
    panel = _panel()
    for scheme in ("equal", "inverse_vol"):
        w = carry_portfolio(panel, scheme=scheme, vol_window=60).weights
        assert np.allclose(w.sum(axis=1), 1.0)


def test_inverse_vol_underweights_the_noisy_coin():
    # C2 is 4x as volatile -> inverse-vol should give it the smallest weight.
    panel = _panel(vols=(1e-4, 1e-4, 4e-4))
    r = carry_portfolio(panel, scheme="inverse_vol", vol_window=60)
    last = r.weights.iloc[-1]
    assert last["C2"] < last["C0"] and last["C2"] < last["C1"]


def test_inverse_vol_beats_equal_here():
    # With one noisy coin, risk-balancing should improve the Sharpe vs equal weight.
    panel = _panel(vols=(1e-4, 1e-4, 4e-4))
    eq = carry_portfolio(panel, scheme="equal", vol_window=60).sharpe
    iv = carry_portfolio(panel, scheme="inverse_vol", vol_window=60).sharpe
    assert iv > eq


def test_portfolio_equity_chart_renders_offline():
    # The chart layer should run on a synthetic panel with no network.
    from cryptostat.funding.visualize import plot_portfolio_equity
    fig = plot_portfolio_equity(panel=_panel(vols=(1e-4, 1e-4, 4e-4)), vol_window=60)
    assert fig is not None and len(fig.axes) == 1


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
