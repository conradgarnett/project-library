"""
Charts for the funding-carry strategy (matplotlib, headless).

Purely a presentation layer over results the other modules already compute — it
adds no new analysis. Every function returns a matplotlib Figure and, if
``save_path`` is given, writes a PNG. Nothing calls ``plt.show()``.

Figures
-------
plot_portfolio_equity     : cumulative equity of the carry portfolio.
plot_idealized_vs_basis   : idealized vs basis-aware equity for one coin (the
                            "honesty gap").
plot_funding_over_time    : funding rate per coin across time (regimes).
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .carry import basis_carry_backtest, carry_backtest
from .data import (
    FUNDING_INTERVALS_PER_YEAR,
    funding_history,
    perp_price_history,
    spot_price_history,
)
from .portfolio import carry_portfolio, carry_returns_panel


def _equity(returns) -> pd.Series:
    return (1.0 + returns).cumprod()


def _finish(fig, save_path):
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=130, bbox_inches="tight")
    return fig


# --------------------------------------------------------------------------- #
def plot_portfolio_equity(panel=None, coins=None, scheme="inverse_vol",
                          vol_window=60, save_path=None):
    """
    Portfolio equity curve (both weighting schemes) with the average single-coin
    carry underneath for contrast.
    """
    if panel is None:
        panel = carry_returns_panel(coins or ["BTC", "ETH", "SOL", "DOGE", "XRP", "LTC"])

    fig, ax = plt.subplots(figsize=(11, 6))
    # individual single-coin carries in the background (jagged, varied)
    for i, c in enumerate(panel.columns):
        _equity(panel[c]).plot(ax=ax, lw=0.8, color="#cccccc", alpha=0.8, zorder=1,
                               label="individual coins" if i == 0 else "_nolegend_")
    # the portfolios on top (smoother — the diversification benefit)
    for sch, color in (("equal", "#1f77b4"), ("inverse_vol", "#2ca02c")):
        r = carry_portfolio(panel, scheme=sch, vol_window=vol_window)
        _equity(r.returns).plot(ax=ax, lw=2.2, color=color, zorder=3,
                                label=f"portfolio — {sch} (Sharpe {r.sharpe:.1f})")
    ax.set_title("Funding-carry portfolio — cumulative equity (smoother than any single coin)")
    ax.set_ylabel("equity (×, start = 1.0)")
    ax.set_xlabel("")
    ax.grid(alpha=0.3)
    ax.legend()
    return _finish(fig, save_path)


def plot_idealized_vs_basis(coin="BTC", limit=1000, fee_bps=5.0, save_path=None):
    """Idealized (funding-only) vs basis-aware equity for one coin — the honesty gap."""
    f = funding_history(coin, limit=limit)
    perp = perp_price_history(coin, limit=limit + 200)
    spot = spot_price_history(coin, limit=limit + 200)
    ideal = carry_backtest(f, fee_bps=fee_bps)
    basis = basis_carry_backtest(f, perp, spot, fee_bps=fee_bps)

    fig, ax = plt.subplots(figsize=(11, 6))
    _equity(ideal.returns).plot(ax=ax, lw=2, color="#d62728",
                                label=f"idealized (funding only) — Sharpe {ideal.sharpe:.1f}")
    _equity(basis.returns).plot(ax=ax, lw=2, color="#1f77b4",
                                label=f"basis-aware (honest) — Sharpe {basis.sharpe:.1f}")
    ax.set_title(f"{coin} funding carry — idealized vs basis-aware equity")
    ax.set_ylabel("equity (×, start = 1.0)")
    ax.set_xlabel("")
    ax.grid(alpha=0.3)
    ax.legend()
    return _finish(fig, save_path)


def plot_funding_over_time(coins=None, limit=1000, save_path=None):
    """Annualized funding rate per coin across time, with the zero line (regimes)."""
    coins = coins or ["BTC", "ETH", "SOL", "DOGE", "XRP"]
    ppy = FUNDING_INTERVALS_PER_YEAR
    fig, ax = plt.subplots(figsize=(11, 6))
    for c in coins:
        try:
            f = funding_history(c, limit=limit)["funding_rate"]
        except Exception as e:  # noqa: BLE001
            print(f"  [skip {c}] {type(e).__name__}")
            continue
        # smooth to an annualized rolling rate so the chart is readable
        (f.rolling(21, min_periods=1).mean() * ppy * 100).plot(ax=ax, lw=1.4, label=c)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("Perpetual funding rate over time (7-day avg, annualized)")
    ax.set_ylabel("annualized funding (%)")
    ax.set_xlabel("")
    ax.grid(alpha=0.3)
    ax.legend(ncol=len(coins))
    return _finish(fig, save_path)
