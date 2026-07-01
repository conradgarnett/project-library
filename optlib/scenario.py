"""
Scenario / risk grid: how a position's value, P&L, and Greeks behave across a
grid of spot moves, volatility levels, and time decay.

This is the practical "what happens if" tool — mark a position to market over a
spot × vol grid (optionally rolled forward in time) and read off the P&L and the
aggregate Greeks at every node.

Works with any :class:`optlib.strategy.Strategy` (single option or multi-leg).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .strategy import Leg, Strategy

_METRICS = ("pnl", "value", "delta", "gamma", "vega", "theta", "rho")


@dataclass
class ScenarioResult:
    spots: np.ndarray          # shape (n_spot,)
    vols: np.ndarray           # shape (n_vol,)
    metrics: dict              # metric name -> 2D array, shape (n_vol, n_spot)
    entry_value: float
    T_eval: float

    def frame(self, metric: str = "pnl") -> pd.DataFrame:
        """The chosen metric as a DataFrame (rows = vols, cols = spots)."""
        return pd.DataFrame(
            self.metrics[metric],
            index=[f"{v:.0%}" for v in self.vols],
            columns=[f"{s:.1f}" for s in self.spots],
        )


def _as_strategy(obj) -> Strategy:
    if isinstance(obj, Strategy):
        return obj
    if isinstance(obj, Leg):
        return Strategy("position", [obj])
    raise TypeError("pass a Strategy or a Leg")


def scenario_grid(
    strategy, S0, T, r, sigma0, q=0.0,
    spot_shocks=None, vol_levels=None, days_forward: float = 0.0,
) -> ScenarioResult:
    """
    Build a spot × vol scenario grid for a position.

    Parameters
    ----------
    strategy : a Strategy (or single Leg).
    S0, T, r, sigma0, q : the base/entry market.
    spot_shocks : relative spot moves for the columns (default ±30%).
        The spot axis is ``S0 * (1 + spot_shocks)``.
    vol_levels : absolute vol levels for the rows (default 0.5σ₀ … 1.5σ₀).
    days_forward : calendar days to roll the position forward (time decay);
        the grid is evaluated at ``T - days_forward/365``.

    The reported ``pnl`` is mark-to-market value minus the entry value (the
    position's value at S₀, σ₀, T).
    """
    strat = _as_strategy(strategy)
    if spot_shocks is None:
        spot_shocks = np.linspace(-0.30, 0.30, 31)
    if vol_levels is None:
        vol_levels = np.linspace(0.5 * sigma0, 1.5 * sigma0, 21)
    spot_shocks = np.asarray(spot_shocks, dtype=float)
    vol_levels = np.asarray(vol_levels, dtype=float)

    spots = S0 * (1.0 + spot_shocks)
    T_eval = max(T - days_forward / 365.0, 1e-6)
    entry_value = strat.net_premium(S0, T, r, sigma0, q)

    shape = (vol_levels.size, spots.size)
    out = {m: np.empty(shape) for m in _METRICS}
    for i, vol in enumerate(vol_levels):
        for j, S in enumerate(spots):
            g = strat.greeks(S, T_eval, r, vol, q)
            out["value"][i, j] = g["price"]
            out["pnl"][i, j] = g["price"] - entry_value
            for m in ("delta", "gamma", "vega", "theta", "rho"):
                out[m][i, j] = g[m]

    return ScenarioResult(
        spots=spots, vols=vol_levels, metrics=out,
        entry_value=entry_value, T_eval=T_eval,
    )


def scenario_summary(result: ScenarioResult) -> pd.DataFrame:
    """Best/worst P&L and the Greek ranges observed across the whole grid."""
    rows = []
    for m in _METRICS:
        arr = result.metrics[m]
        rows.append({"metric": m, "min": float(arr.min()),
                     "max": float(arr.max()), "mean": float(arr.mean())})
    return pd.DataFrame(rows)
