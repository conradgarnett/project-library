"""
cryptostat — a crypto statistical-arbitrage research toolkit.

Free, key-less exchange data (Coinbase/Kraken) + cointegration statistics +
pair screening + a lightweight pairs backtester + performance metrics. The
plumbing is done and tested; the trading edge (signal design) is left as
research in ``cryptostat.signals``.

Pipeline:
    data.price_panel  →  pairs.screen_pairs  →  backtest.backtest_pair  →  metrics
"""

from .stats import (
    adf_test,
    engle_granger,
    hedge_ratio,
    half_life,
    zscore,
)
from .data import fetch_ohlcv, price_panel, DEFAULT_UNIVERSE
from .pairs import screen_pairs
from .signals import zscore_signal
from .backtest import backtest_pair, BacktestResult
from .walkforward import walk_forward, WalkForwardResult
from .metrics import performance_summary, sharpe, max_drawdown, equity_curve

__all__ = [
    "adf_test", "engle_granger", "hedge_ratio", "half_life", "zscore",
    "fetch_ohlcv", "price_panel", "DEFAULT_UNIVERSE",
    "screen_pairs", "zscore_signal", "backtest_pair", "BacktestResult",
    "walk_forward", "WalkForwardResult",
    "performance_summary", "sharpe", "max_drawdown", "equity_curve",
]

__version__ = "0.1.0"
