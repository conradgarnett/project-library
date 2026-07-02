"""
Walk-forward portfolio backtest.

Estimate weights on a trailing window, hold them for a rebalance period, then
re-estimate — collecting the out-of-sample portfolio return stream. Never uses
future data. `compare_methods` runs every allocation method head-to-head so you
can see which allocation actually delivers out-of-sample.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .allocate import METHODS, allocate
from .risk import risk_report


def walk_forward(returns: pd.DataFrame, method: str = "risk_parity",
                 lookback: int = 90, rebalance: int = 7, cov_method: str = "ledoit",
                 cost_bps: float = 5.0, **kw):
    """
    Roll the allocation through history. Returns (oos_returns, weights_history).

    lookback  : trailing periods used to estimate weights.
    rebalance : hold each weight set this many periods before re-estimating.
    cost_bps  : turnover cost charged at each rebalance.
    """
    cols = list(returns.columns)
    idx = returns.index
    port = pd.Series(np.nan, index=idx)
    w_hist = {}
    prev_w = pd.Series(0.0, index=cols)

    t = lookback
    while t < len(returns):
        train = returns.iloc[t - lookback:t]
        w = allocate(train, method=method, cov_method=cov_method, **kw).reindex(cols).fillna(0.0)
        w_hist[idx[t]] = w
        end = min(t + rebalance, len(returns))
        seg = returns.iloc[t:end]
        seg_ret = seg.values @ w.values
        # charge turnover cost on the first day of the new allocation
        turnover = float(np.abs(w.values - prev_w.values).sum())
        seg_ret = seg_ret.astype(float)
        if len(seg_ret):
            seg_ret[0] -= turnover * cost_bps / 1e4
        port.iloc[t:end] = seg_ret
        prev_w = w
        t = end

    return port.dropna(), pd.DataFrame(w_hist).T


def compare_methods(returns: pd.DataFrame, methods=METHODS, lookback: int = 90,
                    rebalance: int = 7, cost_bps: float = 5.0,
                    periods_per_year: int = 365) -> dict:
    """
    Walk-forward every method and return {"table": DataFrame of risk reports,
    "returns": {method: oos_return_series}}.
    """
    reports, series = {}, {}
    for m in methods:
        try:
            port, _ = walk_forward(returns, method=m, lookback=lookback,
                                   rebalance=rebalance, cost_bps=cost_bps)
        except Exception as e:  # noqa: BLE001
            print(f"  [skip {m}] {type(e).__name__}: {e}")
            continue
        series[m] = port
        rep = risk_report(port, periods_per_year=periods_per_year).as_dict()
        reports[m] = rep
    table = pd.DataFrame(reports).T
    if len(table):
        table = table.sort_values("sharpe", ascending=False)
    return {"table": table, "returns": series}
