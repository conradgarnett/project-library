"""
Risk & performance metrics for a portfolio return stream.

Value-at-Risk (historical & parametric), Conditional VaR / Expected Shortfall,
drawdown, a simple historical stress test, and the usual performance stats.
All take a 1-D array/Series of per-period returns unless noted.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
from scipy.stats import norm


def _clean(r):
    r = np.asarray(r, dtype=float)
    return r[~np.isnan(r)]


# --------------------------------------------------------------------------- #
# Value at risk / expected shortfall
# --------------------------------------------------------------------------- #
def historical_var(returns, alpha=0.95):
    """Historical VaR at confidence ``alpha`` (a positive loss number)."""
    r = _clean(returns)
    return float(-np.quantile(r, 1.0 - alpha)) if r.size else 0.0


def parametric_var(returns, alpha=0.95):
    """Gaussian (parametric) VaR at confidence ``alpha``."""
    r = _clean(returns)
    if r.size == 0:
        return 0.0
    return float(-(r.mean() + norm.ppf(1.0 - alpha) * r.std(ddof=1)))


def conditional_var(returns, alpha=0.95):
    """Conditional VaR / Expected Shortfall: mean loss in the worst (1−α) tail."""
    r = _clean(returns)
    if r.size == 0:
        return 0.0
    cutoff = np.quantile(r, 1.0 - alpha)
    tail = r[r <= cutoff]
    return float(-tail.mean()) if tail.size else float(-cutoff)


def max_drawdown(returns):
    """Max drawdown fraction (negative) of the compounded equity curve."""
    r = _clean(returns)
    if r.size == 0:
        return 0.0
    eq = np.cumprod(1.0 + r)
    return float((eq / np.maximum.accumulate(eq) - 1.0).min())


def worst_period(returns, window=5):
    """Worst cumulative return over any rolling ``window`` (a simple stress stat)."""
    r = pd.Series(_clean(returns))
    if len(r) < window:
        return float(r.sum())
    roll = (1.0 + r).rolling(window).apply(np.prod, raw=True) - 1.0
    return float(roll.min())


# --------------------------------------------------------------------------- #
# Performance summary
# --------------------------------------------------------------------------- #
@dataclass
class RiskReport:
    ann_return: float
    ann_vol: float
    sharpe: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    worst_week: float
    n_periods: int

    def as_dict(self):
        return asdict(self)


def risk_report(returns, periods_per_year=365) -> RiskReport:
    r = _clean(returns)
    n = r.size
    ann_ret = float((1 + r).prod() ** (periods_per_year / n) - 1) if n else 0.0
    ann_vol = float(r.std(ddof=1) * np.sqrt(periods_per_year)) if n > 1 else 0.0
    sharpe = float(ann_ret / ann_vol) if ann_vol > 0 else 0.0
    return RiskReport(
        ann_return=ann_ret, ann_vol=ann_vol, sharpe=sharpe,
        max_drawdown=max_drawdown(r), var_95=historical_var(r, 0.95),
        cvar_95=conditional_var(r, 0.95), worst_week=worst_period(r, 7),
        n_periods=int(n),
    )
