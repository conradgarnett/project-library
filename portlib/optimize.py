"""
Mean-variance portfolio optimization (Markowitz).

Long-only, fully-invested (weights sum to 1) portfolios by default, solved with
SLSQP. Provides minimum-variance, maximum-Sharpe, and mean-variance-utility
objectives. Optional per-asset weight cap.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def _labels(cov):
    return list(cov.index) if isinstance(cov, pd.DataFrame) else None


def _series(w, cov):
    lab = _labels(cov)
    return pd.Series(w, index=lab) if lab else w


def _constraints_bounds(n, long_only, weight_cap):
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    lo = 0.0 if long_only else -1.0
    hi = weight_cap if weight_cap is not None else (1.0 if long_only else 1.0)
    bounds = [(lo, hi)] * n
    return cons, bounds


def min_variance(cov, long_only=True, weight_cap=None):
    """Global minimum-variance portfolio: minimize wᵀΣw."""
    S = np.asarray(cov, dtype=float)
    n = S.shape[0]
    cons, bounds = _constraints_bounds(n, long_only, weight_cap)
    w0 = np.full(n, 1.0 / n)
    res = minimize(lambda w: w @ S @ w, w0, method="SLSQP",
                   bounds=bounds, constraints=cons,
                   options={"maxiter": 500, "ftol": 1e-12})
    return _series(res.x / res.x.sum(), cov)


def max_sharpe(mean, cov, rf=0.0, long_only=True, weight_cap=None):
    """
    Maximum-Sharpe (tangency) portfolio. ``mean`` is the vector of expected
    per-period returns; ``rf`` the per-period risk-free rate.
    """
    S = np.asarray(cov, dtype=float)
    mu = np.asarray(mean, dtype=float)
    n = S.shape[0]
    cons, bounds = _constraints_bounds(n, long_only, weight_cap)

    def neg_sharpe(w):
        vol = np.sqrt(max(w @ S @ w, 1e-18))
        return -(w @ mu - rf) / vol

    w0 = np.full(n, 1.0 / n)
    res = minimize(neg_sharpe, w0, method="SLSQP",
                   bounds=bounds, constraints=cons,
                   options={"maxiter": 500, "ftol": 1e-12})
    return _series(res.x / res.x.sum(), cov)


def mean_variance(mean, cov, risk_aversion=3.0, long_only=True, weight_cap=None):
    """
    Mean-variance utility portfolio: maximize  wᵀμ − (λ/2)·wᵀΣw.
    Higher ``risk_aversion`` (λ) tilts toward lower variance.
    """
    S = np.asarray(cov, dtype=float)
    mu = np.asarray(mean, dtype=float)
    n = S.shape[0]
    cons, bounds = _constraints_bounds(n, long_only, weight_cap)
    res = minimize(lambda w: -(w @ mu) + 0.5 * risk_aversion * (w @ S @ w),
                   np.full(n, 1.0 / n), method="SLSQP",
                   bounds=bounds, constraints=cons,
                   options={"maxiter": 500, "ftol": 1e-12})
    return _series(res.x / res.x.sum(), cov)
