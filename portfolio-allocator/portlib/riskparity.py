"""
Risk-based allocation: inverse-volatility and (equal-risk-contribution) risk parity.

Risk parity ignores expected returns entirely — it sizes positions so each asset
contributes the *same* amount of risk to the portfolio. That avoids the extreme,
error-sensitive bets mean-variance can make, and is a workhorse allocation for
multi-strategy books.
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


def inverse_vol(cov):
    """Weights ∝ 1/σ_i (naive risk parity — ignores correlations)."""
    S = np.asarray(cov, dtype=float)
    vol = np.sqrt(np.diag(S))
    w = 1.0 / vol
    return _series(w / w.sum(), cov)


def risk_contributions(weights, cov):
    """Per-asset risk contribution; sums to the portfolio volatility."""
    w = np.asarray(weights, dtype=float)
    S = np.asarray(cov, dtype=float)
    port_vol = np.sqrt(w @ S @ w)
    mrc = S @ w / port_vol            # marginal risk contribution
    rc = w * mrc                      # risk contribution (sums to port_vol)
    if isinstance(cov, pd.DataFrame):
        return pd.Series(rc, index=cov.index)
    return rc


def risk_parity(cov, long_only=True):
    """
    Equal-risk-contribution portfolio: find w (sum=1, w≥0) so every asset
    contributes equal risk. Solved by minimizing the dispersion of risk
    contributions.
    """
    S = np.asarray(cov, dtype=float)
    n = S.shape[0]

    def objective(w):
        port_var = w @ S @ w
        if port_var <= 0:
            return 0.0
        rc = w * (S @ w) / port_var  # RELATIVE risk contributions (sum to 1) — scale-free
        return np.sum((rc - 1.0 / n) ** 2)

    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    bounds = [(1e-6 if long_only else -1.0, 1.0)] * n
    res = minimize(objective, np.full(n, 1.0 / n), method="SLSQP",
                   bounds=bounds, constraints=cons,
                   options={"maxiter": 1000, "ftol": 1e-14})
    return _series(res.x / res.x.sum(), cov)
