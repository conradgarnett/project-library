"""
cryptostat — a crypto arbitrage toolkit, organized by strategy family.

Subpackages
-----------
common/     shared plumbing: market data, cointegration stats, performance metrics
statarb/    statistical arbitrage (cointegration pairs trading) + walk-forward validation
crossvenue/ cross-exchange & triangular/cyclic arbitrage across five free USD venues

Everything runs on free, key-less exchange APIs. The public API below is
re-exported here for convenience (`from cryptostat import backtest_pair`), but
each subpackage can also be imported directly (`from cryptostat.statarb.backtest
import backtest_pair`).

The funding-rate carry strategy lives in its own sibling project on the
`crypto-funding-carry` branch.
"""

# --- common ---------------------------------------------------------------- #
from .common.stats import (
    adf_test, engle_granger, hedge_ratio, half_life, zscore,
)
from .common.data import fetch_ohlcv, price_panel, DEFAULT_UNIVERSE
from .common.metrics import performance_summary, sharpe, max_drawdown, equity_curve

# --- statistical arbitrage ------------------------------------------------- #
from .statarb.pairs import screen_pairs
from .statarb.signals import zscore_signal
from .statarb.backtest import backtest_pair, BacktestResult
from .statarb.walkforward import walk_forward, WalkForwardResult

# --- cross-venue arbitrage ------------------------------------------------- #
from .crossvenue.exchanges import (
    daily_close_panel, live_quote_panel, USD_EXCHANGES, TAKER_FEE_BPS,
)
from .crossvenue.crossexchange import (
    live_arbitrage, scan_live_arbitrage, cross_exchange_spread, dislocation_stats,
)
from .crossvenue.arbgraph import build_edges, find_cycles, scan as scan_triangular

__all__ = [
    # common
    "adf_test", "engle_granger", "hedge_ratio", "half_life", "zscore",
    "fetch_ohlcv", "price_panel", "DEFAULT_UNIVERSE",
    "performance_summary", "sharpe", "max_drawdown", "equity_curve",
    # statarb
    "screen_pairs", "zscore_signal", "backtest_pair", "BacktestResult",
    "walk_forward", "WalkForwardResult",
    # crossvenue
    "daily_close_panel", "live_quote_panel", "USD_EXCHANGES", "TAKER_FEE_BPS",
    "live_arbitrage", "scan_live_arbitrage", "cross_exchange_spread", "dislocation_stats",
    "build_edges", "find_cycles", "scan_triangular",
]

__version__ = "0.3.0"
