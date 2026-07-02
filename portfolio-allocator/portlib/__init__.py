"""
portlib — a portfolio construction & risk toolkit.

Turn a panel of return streams — *assets* (BTC, ETH, …) or your own *strategies*
(funding carry, stat-arb) — into a risk-managed book:

  covariance : sample + Ledoit-Wolf shrinkage
  optimize   : mean-variance (min-variance, max-Sharpe, MV-utility)
  riskparity : inverse-vol + equal-risk-contribution risk parity
  hrp        : Hierarchical Risk Parity (López de Prado)
  allocate   : one `allocate(returns, method=...)` interface over all of the above
  risk       : VaR / CVaR / drawdown / stress + performance report
  backtest   : walk-forward rebalancing that compares methods out-of-sample

Free daily data via `portlib.data`, or feed your own returns CSV.
"""

from .covariance import sample_covariance, ledoit_wolf, cov_estimate, correlation_from_cov
from .optimize import min_variance, max_sharpe, mean_variance
from .riskparity import inverse_vol, risk_parity, risk_contributions
from .hrp import hrp_weights
from .allocate import allocate, METHODS
from .risk import (
    risk_report, RiskReport, historical_var, parametric_var, conditional_var,
    max_drawdown, worst_period,
)
from .backtest import walk_forward, compare_methods
from .data import price_panel, returns_panel, load_returns_csv, DEFAULT_UNIVERSE
from .visualize import plot_method_equity, plot_weights

__all__ = [
    "sample_covariance", "ledoit_wolf", "cov_estimate", "correlation_from_cov",
    "min_variance", "max_sharpe", "mean_variance",
    "inverse_vol", "risk_parity", "risk_contributions", "hrp_weights",
    "allocate", "METHODS",
    "risk_report", "RiskReport", "historical_var", "parametric_var",
    "conditional_var", "max_drawdown", "worst_period",
    "walk_forward", "compare_methods",
    "price_panel", "returns_panel", "load_returns_csv", "DEFAULT_UNIVERSE",
    "plot_method_equity", "plot_weights",
]

__version__ = "0.1.0"
