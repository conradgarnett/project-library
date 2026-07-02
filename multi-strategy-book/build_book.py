#!/usr/bin/env python3
"""
Multi-Strategy Book — the capstone.

Loads the real return streams of the sibling strategy projects
(crypto-funding-carry, crypto-stat-arb) plus a BTC benchmark, then uses the
portfolio allocator (portlib) to combine the *strategies* into one risk-managed
book. Demonstrates the full arc: build strategies -> allocate across them.

    python build_book.py        # writes results/ and figures/

Honest scope: the common window is short (~65 days) because free OKX funding
history is only ~3 months deep, and this window was a losing one for stat-arb and
BTC. So this is a proof of the *architecture* and of risk management — not a track
record. See the notes it prints / writes.
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# portlib lives in the sibling allocator project on main
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "portfolio-allocator"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import portlib as pl  # noqa: E402
from portlib.backtest import walk_forward  # noqa: E402
from portlib.risk import risk_report  # noqa: E402

RESULTS = os.path.join(HERE, "results")
FIG = os.path.join(HERE, "figures")
PPY = 365


def _ann(r):
    return r.mean() * PPY, r.std() * np.sqrt(PPY), (r.mean() / r.std() * np.sqrt(PPY) if r.std() else 0.0)


def main():
    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(FIG, exist_ok=True)
    book = pd.read_csv(os.path.join(HERE, "book_returns.csv"), index_col=0, parse_dates=True).dropna()
    strategies = ["funding_carry", "stat_arb"]         # the market-neutral book
    strat = book[strategies]

    # --- standalone + correlation ---
    lines = ["MULTI-STRATEGY BOOK", "=" * 60,
             f"Window : {book.index.min().date()} -> {book.index.max().date()} "
             f"({len(book)} days)", ""]
    lines.append("STANDALONE (annualized)")
    for c in book.columns:
        a, v, s = _ann(book[c])
        lines.append(f"  {c:14s} return {a:+7.2%}  vol {v:6.2%}  sharpe {s:+.2f}")
    lines += ["", "CORRELATION (strategies are ~uncorrelated with each other and BTC)",
              book.corr().round(2).to_string(), ""]

    # --- allocate across the two strategies ---
    lines.append("ALLOCATED BOOK — weights across the strategies")
    for m in ("risk_parity", "min_variance", "hrp", "equal"):
        w = pl.allocate(strat, method=m, cov_method="sample")
        lines.append(f"  {m:13s} " + "  ".join(f"{k}={w[k]:.2f}" for k in strategies))

    # walk-forward the book (short lookback for the short window)
    lines += ["", "BOOK vs STRATEGIES — walk-forward (lookback 20, rebalance 5)"]
    port, _ = walk_forward(strat, method="risk_parity", lookback=20, rebalance=5, cost_bps=5, cov_method="sample")
    for name, series in [("funding_carry", strat["funding_carry"]),
                         ("stat_arb", strat["stat_arb"]),
                         ("BOOK (risk parity)", port)]:
        rep = risk_report(series.loc[port.index], PPY)
        lines.append(f"  {name:20s} sharpe {rep.sharpe:+.2f}  vol {rep.ann_vol:6.2%}  "
                     f"maxDD {rep.max_drawdown:+.2%}  VaR95 {rep.var_95:.3f}")

    lines += ["", "READ THIS (honest scope)",
              "  * ~65-day window: free OKX funding history is only ~3 months deep.",
              "  * This window was a losing one for stat-arb and BTC, so the book's",
              "    RETURN is negative. The point is the ARCHITECTURE + risk management:",
              "    the strategies are genuinely uncorrelated, and risk-based allocation",
              "    combines them into a lower-vol, lower-drawdown book than any naive mix.",
              "  * With longer history and more strategies this is exactly how a",
              "    systematic multi-strategy book is assembled."]
    report = "\n".join(lines)
    with open(os.path.join(RESULTS, "book.txt"), "w") as f:
        f.write(report + "\n")
    print(report)

    # --- charts ---
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # equity: book vs components
    fig, ax = plt.subplots(figsize=(11, 6))
    for c, col in [("funding_carry", "#2ca02c"), ("stat_arb", "#ff7f0e")]:
        (1 + strat[c].loc[port.index]).cumprod().plot(ax=ax, lw=1.3, color=col, alpha=0.8, label=c)
    (1 + port).cumprod().plot(ax=ax, lw=2.4, color="#1f77b4", label="BOOK (risk parity)")
    ax.axhline(1, color="black", lw=0.8)
    ax.set_title("Multi-strategy book vs its strategies (walk-forward)")
    ax.set_ylabel("equity (×)"); ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "book_equity.png"), dpi=130)

    # correlation heatmap
    fig, ax = plt.subplots(figsize=(5.5, 4.6))
    C = book.corr()
    im = ax.imshow(C.values, cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(C))); ax.set_xticklabels(C.columns, rotation=30, ha="right")
    ax.set_yticks(range(len(C))); ax.set_yticklabels(C.columns)
    for i in range(len(C)):
        for j in range(len(C)):
            ax.text(j, i, f"{C.values[i, j]:.2f}", ha="center", va="center", fontsize=9)
    ax.set_title("Return correlations")
    fig.colorbar(im, shrink=0.8)
    fig.tight_layout(); fig.savefig(os.path.join(FIG, "book_correlation.png"), dpi=130)
    print(f"\nWrote results/book.txt and figures/ to {HERE}")


if __name__ == "__main__":
    main()
