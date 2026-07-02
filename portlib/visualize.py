"""
Charts for the allocator (matplotlib, headless). Presentation only.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_method_equity(returns_by_method: dict, save_path=None):
    """
    Out-of-sample equity curve for each allocation method (from
    ``backtest.compare_methods()["returns"]``).
    """
    fig, ax = plt.subplots(figsize=(11, 6))
    order = sorted(returns_by_method.items(),
                   key=lambda kv: (1 + kv[1]).prod(), reverse=True)
    for name, r in order:
        eq = (1 + r).cumprod()
        final = eq.iloc[-1]
        ax.plot(eq.index, eq.values, lw=1.8, label=f"{name}  (×{final:.2f})")
    ax.axhline(1.0, color="black", lw=0.8, alpha=0.6)
    ax.set_title("Allocation methods — out-of-sample equity (walk-forward)")
    ax.set_ylabel("equity (×, start = 1.0)")
    ax.grid(alpha=0.3)
    ax.legend()
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=130, bbox_inches="tight")
    return fig


def plot_efficient_frontier(returns, cov=None, periods_per_year=365,
                            rf=0.0, long_only=True, save_path=None):
    """
    The efficient frontier with the individual assets and every allocation
    method's portfolio marked on the risk/return plane. Axes are annualized.
    """
    from .allocate import METHODS, allocate
    from .covariance import cov_estimate
    from .frontier import efficient_frontier, portfolio_point

    mu = returns.mean().values
    S = np.asarray(cov if cov is not None else cov_estimate(returns))
    ann_r = periods_per_year
    ann_v = np.sqrt(periods_per_year)

    fr = efficient_frontier(mu, S, n_points=60, long_only=long_only, rf=rf)

    fig, ax = plt.subplots(figsize=(11, 7))
    # frontier
    ax.plot(fr["vol"] * ann_v, fr["ret"] * ann_r, "-", color="#333333", lw=2,
            label="efficient frontier", zorder=2)
    # individual assets
    asset_vol = np.sqrt(np.diag(S)) * ann_v
    ax.scatter(asset_vol, mu * ann_r, s=30, color="#bbbbbb", zorder=1)
    for name, x, y in zip(returns.columns, asset_vol, mu * ann_r):
        ax.annotate(name, (x, y), fontsize=7, color="#888888",
                    xytext=(3, 3), textcoords="offset points")
    # capital market line (through rf and the tangency portfolio)
    tv, tr, _ = fr["tangency"]
    xs = np.linspace(0, fr["vol"].max(), 50)
    cml = rf * ann_r + (tr - rf) / tv * xs
    ax.plot(xs * ann_v, cml * ann_r, ls="--", color="#2ca02c", lw=1.2, alpha=0.8,
            label="capital market line")
    # method portfolios
    markers = {"min_variance": ("D", "#ff7f0e"), "max_sharpe": ("*", "#d62728"),
               "risk_parity": ("o", "#1f77b4"), "hrp": ("s", "#9467bd"),
               "inverse_vol": ("^", "#17becf"), "equal": ("P", "#8c564b")}
    for m in METHODS:
        w = allocate(returns, method=m).reindex(returns.columns).fillna(0).values
        v, r = portfolio_point(w, mu, S)
        mk, col = markers.get(m, ("o", "black"))
        ax.scatter(v * ann_v, r * ann_r, marker=mk, s=140 if mk == "*" else 90,
                   color=col, edgecolor="black", linewidth=0.5, zorder=4, label=m)

    ax.set_title("Efficient frontier & allocation methods (annualized)")
    ax.set_xlabel("volatility (annualized)")
    ax.set_ylabel("expected return (annualized)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=130, bbox_inches="tight")
    return fig


def plot_weights(weights, title="Portfolio weights", save_path=None):
    """Horizontal bar chart of a weight Series."""
    w = weights.sort_values()
    fig, ax = plt.subplots(figsize=(8, max(3, 0.4 * len(w))))
    ax.barh(w.index, w.values, color="#1f77b4")
    ax.set_title(title)
    ax.set_xlabel("weight")
    ax.grid(alpha=0.3, axis="x")
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=130, bbox_inches="tight")
    return fig
