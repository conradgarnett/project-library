"""
Unified allocation interface.

`allocate(returns, method=...)` estimates a covariance (and mean, where needed)
from a returns panel and returns portfolio weights for the chosen method:

    equal | inverse_vol | min_variance | max_sharpe | risk_parity | hrp

The same call works whether the columns are *assets* (BTC, ETH, …) or your own
*strategies* (funding carry, stat-arb) — allocation is return-stream agnostic,
which is the whole point of a multi-strategy book.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .covariance import cov_estimate
from .hrp import hrp_weights
from .optimize import max_sharpe, min_variance
from .riskparity import inverse_vol, risk_parity

METHODS = ("equal", "inverse_vol", "min_variance", "max_sharpe", "risk_parity", "hrp")


def allocate(returns: pd.DataFrame, method: str = "risk_parity",
             cov_method: str = "ledoit", long_only: bool = True,
             weight_cap=None, rf: float = 0.0) -> pd.Series:
    """Return portfolio weights (a Series indexed by column) for ``method``."""
    if method not in METHODS:
        raise ValueError(f"method must be one of {METHODS}")
    cols = list(returns.columns)

    if method == "equal":
        return pd.Series(np.full(len(cols), 1.0 / len(cols)), index=cols)

    cov = cov_estimate(returns, method=cov_method)

    if method == "inverse_vol":
        return inverse_vol(cov)
    if method == "min_variance":
        return min_variance(cov, long_only=long_only, weight_cap=weight_cap)
    if method == "max_sharpe":
        mean = returns.mean().values
        return max_sharpe(mean, cov, rf=rf, long_only=long_only, weight_cap=weight_cap)
    if method == "risk_parity":
        return risk_parity(cov, long_only=long_only)
    if method == "hrp":
        return hrp_weights(cov)
