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
