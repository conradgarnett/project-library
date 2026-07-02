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

Two backtest models:
  * ``carry_backtest``      — IDEALIZED: assumes a perfect hedge, so the return
    is just the funding collected. Optimistic (inflates Sharpe).
  * ``basis_carry_backtest`` — BASIS-AWARE: uses the real perp & spot price paths,
    so the return includes the actual price-leg P&L (= -Δbasis). This is the
    honest model. Even a tiny same-venue basis (vol < 1 bp) meaningfully cuts the
    Sharpe, because the per-8h funding drip is itself tiny — the basis *changes*
    dominate the return variance.

Still not modeled (perp-leg liquidation risk, exchange/counterparty risk); see
the README "Next steps".
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from ..common.metrics import max_drawdown, sharpe
from .data import (
    FUNDING_INTERVALS_PER_YEAR,
    funding_history,
    perp_price_history,
    spot_price_history,
)


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
    basis_aware: bool = False       # True if the spot/perp basis P&L is included
    basis_mean_bps: float | None = None
    basis_vol_bps: float | None = None

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("returns")
        return d

    def summary(self) -> str:
        model = "basis-aware" if self.basis_aware else "idealized (funding only)"
        lines = [
            f"Funding carry ({'flip' if self.flip else 'long-basis'}, {model}), "
            f"{self.n_intervals} intervals",
            f"  annualized yield (simple)     : {self.ann_yield_simple:6.2%}",
            f"  annualized return (compounded): {self.ann_return_compounded:6.2%}",
            f"  Sharpe                        : {self.sharpe:6.2f}",
            f"  max drawdown                  : {self.max_drawdown:6.2%}",
            f"  intervals collecting (>0)     : {self.pct_intervals_positive:6.1%}",
            f"  raw mean funding (annualized) : {self.mean_funding_annualized:6.2%}",
        ]
        if self.basis_aware:
            lines.append(f"  perp-spot basis (bps)         : "
                         f"mean {self.basis_mean_bps:+.2f}, vol {self.basis_vol_bps:.2f}")
        return "\n".join(lines)


def _build_result(ret, f, flip, basis_aware=False, basis=None) -> CarryResult:
    n = len(ret)
    ppy = FUNDING_INTERVALS_PER_YEAR
    return CarryResult(
        returns=ret,
        ann_yield_simple=float(ret.mean() * ppy) if n else 0.0,
        ann_return_compounded=float((1 + ret).prod() ** (ppy / n) - 1) if n else 0.0,
        sharpe=sharpe(ret, periods_per_year=ppy),
        max_drawdown=max_drawdown(ret)[0] if n else 0.0,
        pct_intervals_positive=float((ret > 0).mean()) if n else 0.0,
        mean_funding_annualized=float(f.mean() * ppy) if n else 0.0,
        flip=flip, n_intervals=n, basis_aware=basis_aware,
        basis_mean_bps=(float(basis.mean() * 1e4) if basis is not None else None),
        basis_vol_bps=(float(basis.std() * 1e4) if basis is not None else None),
    )


def _as_rate(funding):
    f = funding["funding_rate"] if isinstance(funding, pd.DataFrame) else funding
    return f.dropna().astype(float)


def carry_backtest(funding, fee_bps: float = 5.0, flip: bool = False) -> CarryResult:
    """
    **Idealized** delta-neutral funding carry: assumes a perfect hedge, so the
    return each interval is just the funding collected minus fees. Optimistic —
    it ignores spot/perp basis moves (see :func:`basis_carry_backtest`).
    """
    f = _as_rate(funding)
    fee = fee_bps / 1e4
    if flip:
        gross = f.abs()                              # always collect the magnitude
        side = np.sign(f).replace(0, 1)
        cost = (side.diff().abs() > 0).astype(float) * fee
        if len(cost):
            cost.iloc[0] = fee                       # initial setup
    else:
        gross = f.copy()                             # short-perp: +funding if >0, pay if <0
        cost = pd.Series(0.0, index=f.index)
        if len(cost):
            cost.iloc[0] = fee
    return _build_result(gross - cost, f, flip)


def basis_carry_backtest(funding, perp_price, spot_price,
                         fee_bps: float = 5.0, flip: bool = False) -> CarryResult:
    """
    **Basis-aware** delta-neutral funding carry — the honest version.

    Uses the actual perp and spot price paths so the return each interval is the
    funding collected **plus the real P&L of the two price legs**. For a
    long-spot / short-perp position that price P&L equals ``-Δ(basis)`` where
    ``basis = perp/spot − 1``:

        return_t = σ · (funding_t − Δbasis_t) − flip_cost

    with σ = +1 (long-basis) or σ = sign(funding) (flip). When the hedge is
    within one venue the basis is tiny, so this barely dents the Sharpe — but it
    is the correct model, and it exposes basis risk when hedging across venues.

    ``perp_price`` / ``spot_price`` are time-indexed Series; they are aligned to
    the funding timestamps.
    """
    f = _as_rate(funding)
    perp = perp_price.reindex(f.index)
    spot = spot_price.reindex(f.index)
    keep = f.notna() & perp.notna() & spot.notna()
    f, perp, spot = f[keep], perp[keep], spot[keep]

    basis = perp / spot - 1.0                        # perp premium over spot
    dbasis = basis.diff().fillna(0.0)
    sigma = np.sign(f).replace(0, 1) if flip else pd.Series(1.0, index=f.index)

    gross = sigma * (f - dbasis)
    fee = fee_bps / 1e4
    if flip:
        cost = (sigma.diff().abs() > 0).astype(float) * fee
    else:
        cost = pd.Series(0.0, index=f.index)
    if len(cost):
        cost.iloc[0] = fee
    return _build_result(gross - cost, f, flip, basis_aware=True, basis=basis)


def compare_carry(coin: str = "BTC", limit: int = 1000, fee_bps: float = 5.0,
                  flip: bool = False) -> dict:
    """
    Fetch funding + perp + spot for a coin and run BOTH the idealized and the
    basis-aware carry, so the Sharpe gap (the cost of the perfect-hedge
    assumption) is explicit. Returns {"idealized": CarryResult, "basis": CarryResult}.
    """
    f = funding_history(coin, limit=limit)
    perp = perp_price_history(coin, limit=limit + 200)
    spot = spot_price_history(coin, limit=limit + 200)
    return {
        "idealized": carry_backtest(f, fee_bps=fee_bps, flip=flip),
        "basis": basis_carry_backtest(f, perp, spot, fee_bps=fee_bps, flip=flip),
    }
