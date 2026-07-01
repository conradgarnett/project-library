"""
Lightweight pairs backtest engine.

Given two price series and a hedge ratio, it forms the spread, hands the rolling
z-score to a signal function, and simulates trading the dollar-neutral pair with
transaction costs. Vectorized and intentionally simple — realistic *enough* to
compare signal ideas, while leaving richer execution modeling as an extension.

Key modeling choices (documented so you can make them more realistic):
  * The spread is  A - β·B ; a +1 position is long A / short β·B.
  * P&L per period = position(t-1) · Δspread(t), expressed as a return on the
    gross notional of the two legs at entry (so Sharpe etc. are well-defined).
  * Costs = ``cost_bps`` charged on the traded notional whenever the position
    changes (a proxy for fees + half-spread).
  * No look-ahead: the position is shifted one period before it earns P&L, and
    the z-score is trailing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .signals import zscore_signal
from .stats import hedge_ratio, zscore


@dataclass
class BacktestResult:
    returns: pd.Series          # per-period strategy returns
    position: pd.Series         # {-1,0,+1} spread position
    spread: pd.Series
    zscore: pd.Series
    beta: float
    n_trades: int
    turnover: float


def backtest_pair(
    price_a, price_b, beta=None, hedge_method="ols",
    z_window=30, entry=2.0, exit=0.5, stop=None,
    cost_bps=10.0, signal_fn=None,
) -> BacktestResult:
    """
    Backtest one pair (A, B) with the baseline (or a custom) signal.

    Parameters
    ----------
    price_a, price_b : aligned price Series (same index).
    beta : hedge ratio; if None it is estimated on the full sample by
        ``hedge_method`` ("ols"/"tls"). NOTE: full-sample beta peeks at the
        future — fine for a first pass, but see the walk-forward note in README.
    z_window : trailing window for the spread z-score.
    entry/exit/stop : passed to the signal.
    cost_bps : per-trade cost on traded notional, in basis points.
    signal_fn : callable(z_array) -> position array; defaults to zscore_signal.
    """
    a = pd.Series(np.asarray(price_a, dtype=float))
    b = pd.Series(np.asarray(price_b, dtype=float))
    idx = price_a.index if isinstance(price_a, pd.Series) else a.index

    if beta is None:
        beta = hedge_ratio(a.values, b.values, method=hedge_method)

    spread = a.values - beta * b.values
    z = zscore(spread, window=z_window)

    if signal_fn is None:
        pos = zscore_signal(z, entry=entry, exit=exit, stop=stop)
    else:
        pos = np.asarray(signal_fn(z), dtype=float)

    # Gross notional of the two legs (for return normalization).
    gross = np.abs(a.values) + np.abs(beta) * np.abs(b.values)
    dspread = np.diff(spread, prepend=spread[0])
    # P&L uses the *previous* period's position (no look-ahead).
    pos_lag = np.concatenate([[0.0], pos[:-1]])
    pnl = pos_lag * dspread
    ret = np.divide(pnl, gross, out=np.zeros_like(pnl), where=gross > 0)

    # Transaction costs when the position changes.
    dpos = np.abs(np.diff(pos, prepend=0.0))
    cost = dpos * (cost_bps / 1e4)
    ret = ret - cost

    n_trades = int((dpos > 0).sum())
    turnover = float(dpos.sum())

    return BacktestResult(
        returns=pd.Series(ret, index=idx),
        position=pd.Series(pos, index=idx),
        spread=pd.Series(spread, index=idx),
        zscore=pd.Series(z, index=idx),
        beta=float(beta),
        n_trades=n_trades,
        turnover=turnover,
    )
