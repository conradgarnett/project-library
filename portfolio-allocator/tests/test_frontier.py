"""Efficient frontier — shape and special-point properties (offline)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from portlib.covariance import cov_estimate  # noqa: E402
from portlib.frontier import efficient_frontier, portfolio_point  # noqa: E402


def _data(seed=0):
    rng = np.random.default_rng(seed)
    mu = np.array([0.0002, 0.0004, 0.0006, 0.0008])
    vols = np.array([0.01, 0.015, 0.02, 0.03])
    X = rng.standard_normal((900, 4)) * vols + mu
    df = pd.DataFrame(X, columns=list("ABCD"))
    return df.mean().values, np.asarray(cov_estimate(df))


def test_min_var_is_leftmost():
    mu, S = _data()
    fr = efficient_frontier(mu, S, n_points=40)
    assert abs(fr["min_var"][0] - fr["vol"].min()) < 1e-9


def test_upper_branch_is_monotone():
    mu, S = _data()
    fr = efficient_frontier(mu, S, n_points=50)
    i = int(np.argmin(fr["vol"]))
    up_v = fr["vol"][i:]
    assert np.all(np.diff(up_v) >= -1e-9)          # vol rises as return rises above min-var


def test_tangency_beats_every_asset_sharpe():
    mu, S = _data()
    fr = efficient_frontier(mu, S, n_points=60)
    tan_sharpe = fr["tangency"][1] / fr["tangency"][0]
    asset_sharpe = (mu / np.sqrt(np.diag(S))).max()
    assert tan_sharpe >= asset_sharpe - 1e-6


def test_frontier_weights_sum_to_one():
    mu, S = _data()
    fr = efficient_frontier(mu, S, n_points=30)
    for w in fr["weights"]:
        assert abs(np.sum(w) - 1.0) < 1e-6 and (w >= -1e-9).all()


def test_portfolio_point_matches_manual():
    mu, S = _data()
    w = np.array([0.25, 0.25, 0.25, 0.25])
    v, r = portfolio_point(w, mu, S)
    assert abs(v - np.sqrt(w @ S @ w)) < 1e-12 and abs(r - w @ mu) < 1e-12


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
