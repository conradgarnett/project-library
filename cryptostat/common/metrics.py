"""
Performance metrics for a strategy's return stream.

All functions take a 1-D array/Series of per-period returns (or P&L) and an
``periods_per_year`` for annualization (365 for daily crypto, which trades every
day; 252 for equities; 24*365 for hourly, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd


def _clean(returns):
    r = np.asarray(returns, dtype=float)
    return r[~np.isnan(r)]


def sharpe(returns, periods_per_year=365, rf=0.0):
    r = _clean(returns) - rf / periods_per_year
    sd = r.std(ddof=1)
    return float(np.sqrt(periods_per_year) * r.mean() / sd) if sd > 0 else 0.0


def sortino(returns, periods_per_year=365, rf=0.0):
    r = _clean(returns) - rf / periods_per_year
    downside = r[r < 0]
    dd = np.sqrt((downside ** 2).mean()) if downside.size else 0.0
    return float(np.sqrt(periods_per_year) * r.mean() / dd) if dd > 0 else 0.0


def max_drawdown(returns):
    """Return (max_drawdown_fraction, peak_index, trough_index) on the equity curve."""
    r = _clean(returns)
    equity = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1.0
    trough = int(np.argmin(dd))
    peak_i = int(np.argmax(equity[:trough + 1])) if trough > 0 else 0
    return float(dd.min()), peak_i, trough


def calmar(returns, periods_per_year=365):
    r = _clean(returns)
    ann_return = (1.0 + r).prod() ** (periods_per_year / max(len(r), 1)) - 1.0
    mdd = abs(max_drawdown(r)[0])
    return float(ann_return / mdd) if mdd > 0 else 0.0


def annualized_return(returns, periods_per_year=365):
    r = _clean(returns)
    return float((1.0 + r).prod() ** (periods_per_year / max(len(r), 1)) - 1.0)


def annualized_vol(returns, periods_per_year=365):
    return float(_clean(returns).std(ddof=1) * np.sqrt(periods_per_year))


def hit_rate(returns):
    r = _clean(returns)
    nz = r[r != 0]
    return float((nz > 0).mean()) if nz.size else 0.0


@dataclass
class Performance:
    ann_return: float
    ann_vol: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    hit_rate: float
    n_periods: int

    def as_dict(self):
        return asdict(self)


def performance_summary(returns, periods_per_year=365) -> Performance:
    """One-shot tearsheet of the standard metrics."""
    r = _clean(returns)
    return Performance(
        ann_return=annualized_return(r, periods_per_year),
        ann_vol=annualized_vol(r, periods_per_year),
        sharpe=sharpe(r, periods_per_year),
        sortino=sortino(r, periods_per_year),
        calmar=calmar(r, periods_per_year),
        max_drawdown=max_drawdown(r)[0],
        hit_rate=hit_rate(r),
        n_periods=int(len(r)),
    )


def equity_curve(returns):
    """Cumulative equity (starting at 1.0) as a pandas Series if possible."""
    r = returns
    idx = r.index if isinstance(r, pd.Series) else None
    eq = np.cumprod(1.0 + _clean(np.asarray(r, dtype=float)))
    return pd.Series(eq, index=idx) if idx is not None else eq
