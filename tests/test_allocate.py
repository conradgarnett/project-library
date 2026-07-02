"""Allocation methods & covariance — validated offline on synthetic returns."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from portlib.allocate import METHODS, allocate  # noqa: E402
from portlib.covariance import cov_estimate, ledoit_wolf  # noqa: E402
from portlib.riskparity import risk_contributions  # noqa: E402


def _panel(vols=(0.01, 0.02, 0.03, 0.04, 0.05), n=600, seed=0, means=None):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, len(vols))) * np.asarray(vols)
    if means is not None:
        X = X + np.asarray(means)
    return pd.DataFrame(X, columns=[f"A{i}" for i in range(len(vols))])


def test_ledoit_wolf_psd_and_delta_range():
    cov, delta = ledoit_wolf(_panel())
    assert 0.0 <= delta <= 1.0
    assert np.all(np.linalg.eigvalsh(np.asarray(cov)) >= -1e-10)


def test_all_methods_valid_weights():
    df = _panel()
    for m in METHODS:
        w = allocate(df, method=m)
        assert abs(w.sum() - 1.0) < 1e-6, (m, w.sum())
        assert (w >= -1e-9).all(), (m, w.min())     # long-only


def test_min_variance_overweights_low_vol():
    w = allocate(_panel(), method="min_variance")
    assert w.idxmax() == "A0"                        # A0 has the lowest vol


def test_risk_parity_equalizes_contributions():
    df = _panel()
    w = allocate(df, method="risk_parity")
    rc = risk_contributions(w, cov_estimate(df))
    rc = rc / rc.sum()
    assert np.allclose(rc.values, 1.0 / len(rc), atol=0.02)


def test_inverse_vol_matches_formula():
    # With the sample covariance, inverse-vol == (1/sample_std) normalized.
    df = _panel()
    w = allocate(df, method="inverse_vol", cov_method="sample")
    inv = 1.0 / df.std(ddof=1).values
    assert np.allclose(w.values, inv / inv.sum(), atol=1e-6)


def test_max_sharpe_prefers_high_return_low_vol():
    # A4 gets a strong positive mean at the *lowest* implied noise weighting.
    df = _panel(means=[0, 0, 0, 0, 0.02])
    w = allocate(df, method="max_sharpe")
    assert w["A4"] > 0.5


def test_hrp_positive_and_sums_to_one():
    w = allocate(_panel(), method="hrp")
    assert abs(w.sum() - 1.0) < 1e-6 and (w > 0).all()


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
