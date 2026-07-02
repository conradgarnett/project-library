"""
cryptostat.funding — crypto perpetual-futures funding-rate carry.

A delta-neutral strategy that harvests the funding paid by perpetual swaps: hold
long spot + short perp so price exposure cancels, and collect the recurring
funding payment. Unlike arbitrage, this is a *risk premium* — it persists and is
not latency-bound.

Subpackages
-----------
common/   shared plumbing: market data, performance metrics (+ cointegration
          stats, shared with the sibling arbitrage project)
funding/  OKX funding-rate data + the delta-neutral carry backtest

Runs on free, key-less exchange APIs. Public API is re-exported here.
"""

from .common.data import fetch_ohlcv, price_panel, DEFAULT_UNIVERSE
from .common.metrics import performance_summary, sharpe, max_drawdown, equity_curve
from .funding.data import (
    funding_history, funding_now, OKX_FUNDING_INTERVAL_H, FUNDING_INTERVALS_PER_YEAR,
)
from .funding.carry import carry_backtest, CarryResult

__all__ = [
    "fetch_ohlcv", "price_panel", "DEFAULT_UNIVERSE",
    "performance_summary", "sharpe", "max_drawdown", "equity_curve",
    "funding_history", "funding_now", "OKX_FUNDING_INTERVAL_H",
    "FUNDING_INTERVALS_PER_YEAR", "carry_backtest", "CarryResult",
]

__version__ = "0.1.0"
