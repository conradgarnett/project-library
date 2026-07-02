"""Cointegration statistics — validated on synthetic series with known truth."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from cryptostat.common.stats import (  # noqa: E402
    adf_test,
    engle_granger,
    half_life,
    hedge_ratio,
    zscore,
)


def test_adf_distinguishes_stationary_from_random_walk():
    rng = np.random.default_rng(0)
    rw = np.cumsum(rng.standard_normal(800))
    wn = rng.standard_normal(800)
    assert not adf_test(rw).is_stationary()       # unit root not rejected
    assert adf_test(wn).is_stationary()           # white noise is stationary
    assert adf_test(wn).stat < adf_test(rw).stat


def test_engle_granger_detects_cointegration():
    rng = np.random.default_rng(1)
    x = np.cumsum(rng.standard_normal(800)) + 50
    y = 2.0 * x + rng.standard_normal(800) * 0.8 + 10      # cointegrated with x
    r = engle_granger(y, x)
    assert r.is_cointegrated()
    assert abs(r.beta - 2.0) < 0.1


def test_engle_granger_rejects_independent_walks():
    rng = np.random.default_rng(2)
    x = np.cumsum(rng.standard_normal(800))
    y = np.cumsum(rng.standard_normal(800))               # independent
    assert not engle_granger(y, x).is_cointegrated()


def test_half_life_recovers_ou_speed():
    rng = np.random.default_rng(3)
    theta, n = 0.05, 4000
    s = np.zeros(n)
    for t in range(1, n):
        s[t] = s[t - 1] - theta * s[t - 1] + rng.standard_normal() * 0.5
    hl = half_life(s)
    true_hl = np.log(2) / theta
    assert abs(hl - true_hl) / true_hl < 0.2      # within 20%


def test_half_life_infinite_for_random_walk():
    rng = np.random.default_rng(4)
    assert half_life(np.cumsum(rng.standard_normal(1000))) == np.inf or \
        half_life(np.cumsum(rng.standard_normal(1000))) > 200


def test_hedge_ratio_ols_and_tls():
    rng = np.random.default_rng(5)
    x = np.cumsum(rng.standard_normal(500)) + 100
    y = 1.5 * x + rng.standard_normal(500) * 0.3
    assert abs(hedge_ratio(y, x, "ols") - 1.5) < 0.05
    assert abs(hedge_ratio(y, x, "tls") - 1.5) < 0.05


def test_zscore_full_and_rolling():
    x = np.array([1.0, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    z = zscore(x)
    assert abs(z.mean()) < 1e-9 and abs(z.std() - 1.0) < 1e-9
    zr = zscore(x, window=5)
    assert np.isnan(zr[:4]).all() and not np.isnan(zr[4:]).any()


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
