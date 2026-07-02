"""
Delta-neutral funding-rate carry backtest.

The trade: hold long spot + short perp (or the reverse), so price exposure
cancels and you simply **collect the funding payment** each interval. This module
turns a funding-rate history into the carry P&L stream and its statistics.

Two modes:
  * ``flip=False`` — always long-spot / short-perp. Collect funding when it's
    positive (the usual state); *pay* it when it flips negative. This is the
    honest "naive carry" and its drawdowns show funding-regime risk.
  * ``flip=True``  — always position to collect: when funding turns negative,
    switch sides (short-spot / long-perp) to earn its magnitude, paying a
    rebalance fee on each switch.

Modeling assumptions (documented so they can be made more realistic):
  * The spot/perp hedge is perfect, so price P&L is ~0 and the return per
    interval is just the funding collected minus fees. Real hedges have basis
    drift and the perp leg carries liquidation risk.
  * ``fee_bps`` is charged once at setup (naive) or on each side flip.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from ..common.metrics import max_drawdown, sharpe
from .data import FUNDING_INTERVALS_PER_YEAR


@dataclass
class CarryResult:
    returns: pd.Series          # per-interval carry return
    ann_yield_simple: float     # mean interval return × intervals/year
    ann_return_compounded: float
    sharpe: float
    max_drawdown: float
    pct_intervals_positive: float
    mean_funding_annualized: float
    flip: bool
    n_intervals: int

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("returns")
        return d

    def summary(self) -> str:
        return (
            f"Funding carry ({'flip' if self.flip else 'long-basis'}), "
            f"{self.n_intervals} intervals\n"
            f"  annualized yield (simple)     : {self.ann_yield_simple:6.2%}\n"
            f"  annualized return (compounded): {self.ann_return_compounded:6.2%}\n"
            f"  Sharpe                        : {self.sharpe:6.2f}\n"
            f"  max drawdown                  : {self.max_drawdown:6.2%}\n"
            f"  intervals collecting (>0)     : {self.pct_intervals_positive:6.1%}\n"
            f"  raw mean funding (annualized) : {self.mean_funding_annualized:6.2%}"
        )


def carry_backtest(funding, fee_bps: float = 5.0, flip: bool = False) -> CarryResult:
    """
    Backtest the delta-neutral funding carry from a funding-rate history.

    ``funding`` is a DataFrame with a ``funding_rate`` column (or a Series) of
    per-interval rates. Returns a :class:`CarryResult`.
    """
    f = funding["funding_rate"] if isinstance(funding, pd.DataFrame) else funding
    f = f.dropna().astype(float)
    fee = fee_bps / 1e4

    if flip:
        gross = f.abs()                              # always collect the magnitude
        side = np.sign(f).replace(0, 1)
        switched = side.diff().abs() > 0
        cost = switched.astype(float) * fee
        if len(cost):
            cost.iloc[0] = fee                       # initial setup
    else:
        gross = f.copy()                             # short-perp: +funding if >0, pay if <0
        cost = pd.Series(0.0, index=f.index)
        if len(cost):
            cost.iloc[0] = fee                       # one-time setup
    ret = gross - cost

    n = len(ret)
    ppy = FUNDING_INTERVALS_PER_YEAR
    ann_simple = float(ret.mean() * ppy) if n else 0.0
    compounded = float((1 + ret).prod() ** (ppy / n) - 1) if n else 0.0
    return CarryResult(
        returns=ret,
        ann_yield_simple=ann_simple,
        ann_return_compounded=compounded,
        sharpe=sharpe(ret, periods_per_year=ppy),
        max_drawdown=max_drawdown(ret)[0] if n else 0.0,
        pct_intervals_positive=float((ret > 0).mean()) if n else 0.0,
        mean_funding_annualized=float(f.mean() * ppy) if n else 0.0,
        flip=flip,
        n_intervals=n,
    )
