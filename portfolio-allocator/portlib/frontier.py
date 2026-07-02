"""
Markowitz efficient frontier.

Traces the set of minimum-variance portfolios for a grid of target returns, then
locates the special portfolios on it (global minimum-variance and the maximum
-Sharpe tangency portfolio). Combined with the per-method points from
``portlib.allocate`` and the individual assets, this is the classic risk/return
picture of the whole opportunity set.

All inputs/outputs are in per-period units; pass ``periods_per_year`` to the
plotter to annualize the axes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize


def _min_var_for_target(S, mu, target, long_only, weight_cap):
    n = len(mu)
    cons = [
        {"type": "eq", "fun": lambda w: np.sum(w) - 1.0},
        {"type": "eq", "fun": lambda w, t=target: w @ mu - t},
    ]
    lo = 0.0 if long_only else -1.0
    hi = weight_cap if weight_cap is not None else 1.0
    res = minimize(lambda w: w @ S @ w, np.full(n, 1.0 / n), method="SLSQP",
                   bounds=[(lo, hi)] * n, constraints=cons,
                   options={"maxiter": 500, "ftol": 1e-12})
    if not res.success:
        return None
    return res.x


def portfolio_point(weights, mean, cov):
    """(volatility, expected return) of a weight vector, per period."""
    w = np.asarray(weights, dtype=float)
    mu = np.asarray(mean, dtype=float)
    S = np.asarray(cov, dtype=float)
    return float(np.sqrt(max(w @ S @ w, 0.0))), float(w @ mu)


def efficient_frontier(mean, cov, n_points: int = 40, long_only: bool = True,
                       weight_cap=None, rf: float = 0.0) -> dict:
    """
    Trace the efficient frontier. Returns a dict with arrays ``vol``, ``ret``,
    ``sharpe`` and a list of ``weights`` along the frontier, plus the global
    minimum-variance (``min_var``) and maximum-Sharpe tangency (``tangency``)
    portfolios as (vol, ret, weights).
    """
    mu = np.asarray(mean, dtype=float)
    S = np.asarray(cov, dtype=float)
    targets = np.linspace(mu.min(), mu.max(), n_points)

    vols, rets, wts = [], [], []
    for t in targets:
        w = _min_var_for_target(S, mu, t, long_only, weight_cap)
        if w is None:
            continue
        v, r = portfolio_point(w, mu, S)
        vols.append(v); rets.append(r); wts.append(w)

    vols = np.asarray(vols); rets = np.asarray(rets)
    sharpe = np.divide(rets - rf, vols, out=np.zeros_like(rets), where=vols > 0)

    i_min = int(np.argmin(vols))
    i_tan = int(np.argmax(sharpe))
    return {
        "vol": vols, "ret": rets, "sharpe": sharpe, "weights": wts,
        "min_var": (vols[i_min], rets[i_min], wts[i_min]),
        "tangency": (vols[i_tan], rets[i_tan], wts[i_tan]),
        "rf": rf,
    }
