#!/usr/bin/env python3
"""
The honest gauntlet for funding-rate carry — real OKX data, real costs,
walk-forward selection only.

This is the same discipline that killed the crypto stat-arb strategy (see the
crypto-stat-arb sibling: honest walk-forward pair selection erased its edge).
Funding carry's premise is different — the funding payment is a *structural*
premium someone chooses to pay, not a pattern mined from noise — but the
premise doesn't get a pass: it is tested the same way.

What is measured (all on cached real data from scripts/… fetch, see README):

  1. per-coin basis-aware carry      the honest single-coin P&L: funding
                                     collected minus the real spot/perp basis
                                     moves, minus entry fees.
  2. hold-all portfolio              equal-weight across the whole universe,
                                     NO selection at all — the zero-selection-
                                     bias benchmark. If the premium is real it
                                     must show up here.
  3. walk-forward selection          every ~30 days, rank coins by TRAILING
                                     mean funding and hold the top K next
                                     period. Selection uses only the past;
                                     switching coins costs real fees (four
                                     legs: close spot+perp, open spot+perp).
  4. yearly subperiods               a premium that only existed in one regime
                                     is a regime bet, not a strategy.

Costs modeled: taker entry on both legs, four-leg switch cost on selection
turnover, and the basis P&L. NOT modeled: perp liquidation risk, spot lending
yield forgone, exchange counterparty risk — all listed in the README.

    python scripts/validate_carry.py
    python scripts/validate_carry.py --top-k 3 --rebalance 90 --trail 270
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from cryptostat.common.metrics import max_drawdown, sharpe  # noqa: E402
from cryptostat.funding.carry import basis_carry_backtest  # noqa: E402
from cryptostat.funding.data import FUNDING_INTERVALS_PER_YEAR  # noqa: E402

PPY = FUNDING_INTERVALS_PER_YEAR          # 1095 eight-hour intervals / year


def load_cached():
    """Load the coins cached by the fetch step: data/funding_<C>.csv etc."""
    coins = sorted(os.path.basename(p)[8:-4]
                   for p in glob.glob(os.path.join(ROOT, "data", "funding_*.csv")))
    out = {}
    for c in coins:
        f = pd.read_csv(os.path.join(ROOT, "data", f"funding_{c}.csv"),
                        index_col=0, parse_dates=True)["funding_rate"]
        # Normalize to the 8h grid: Gate switches volatile contracts to HOURLY
        # funding — floor to the 8h bucket and SUM (hourly payments accrue),
        # so every coin shares the 1095-intervals/year convention.
        f = f.groupby(f.index.floor("8h")).sum()
        p = pd.read_csv(os.path.join(ROOT, "data", f"perp_{c}.csv"),
                        index_col=0, parse_dates=True)["close"]
        s = pd.read_csv(os.path.join(ROOT, "data", f"spot_{c}.csv"),
                        index_col=0, parse_dates=True)["close"]
        out[c] = (f, p, s)
    if not out:
        raise SystemExit("no cached data — run the fetch first (see README)")
    return out


def per_coin_returns(data, fee_bps):
    """Basis-aware per-interval carry returns for every coin, aligned."""
    rets = {}
    for c, (f, p, s) in data.items():
        res = basis_carry_backtest(f.to_frame("funding_rate"), p, s, fee_bps=fee_bps)
        rets[c] = res.returns.rename(c)
    return pd.concat(rets.values(), axis=1, join="inner").dropna()


def stats_line(name, r, extra=""):
    r = np.asarray(r, dtype=float)
    eq = np.cumprod(1 + r)
    ann = float(eq[-1] ** (PPY / len(r)) - 1) if len(r) else 0.0
    print(f"  {name:26s} ann {ann:+7.2%} | Sharpe {sharpe(r, PPY):5.2f} | "
          f"maxDD {max_drawdown(r)[0]:7.2%} | +ivals {(r > 0).mean():5.1%}{extra}")
    return ann, sharpe(r, PPY)


def walk_forward_selection(panel, funding_panel, top_k, trail, rebalance,
                           switch_cost_bps):
    """
    Every ``rebalance`` intervals, pick the ``top_k`` coins by TRAILING mean
    funding over ``trail`` intervals (shifted: the window ends the interval
    before the decision). Hold them equal-weight; charge ``switch_cost_bps``
    on each coin entering/leaving the book (a four-leg swap).
    """
    n = len(panel)
    cols = list(panel.columns)
    ret = np.zeros(n)
    held = set()
    picks_log = []
    t = trail
    while t < n:
        window = funding_panel.iloc[t - trail:t]
        ranked = window.mean().sort_values(ascending=False)
        new = set(ranked.head(top_k).index)
        swaps = len(new - held) + len(held - new)
        end = min(t + rebalance, n)
        seg = panel.iloc[t:end][sorted(new)].mean(axis=1)
        ret[t:end] = seg.to_numpy()
        ret[t] -= (swaps / max(2 * top_k, 1)) * switch_cost_bps / 1e4
        picks_log.append((panel.index[t], sorted(new)))
        held = new
        t = end
    return pd.Series(ret[trail:], index=panel.index[trail:]), picks_log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fee-bps", type=float, default=15.0,
                    help="entry cost per coin (both legs, taker)")
    ap.add_argument("--switch-bps", type=float, default=30.0,
                    help="four-leg cost of swapping one coin for another")
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--trail", type=int, default=90,
                    help="trailing funding window, intervals (90 = 30 days)")
    ap.add_argument("--rebalance", type=int, default=90,
                    help="rebalance cadence, intervals (90 = 30 days)")
    args = ap.parse_args()

    data = load_cached()
    panel = per_coin_returns(data, fee_bps=args.fee_bps)
    funding_panel = pd.concat(
        {c: f for c, (f, _, _) in data.items()}, axis=1).reindex(panel.index)
    years = (panel.index[-1] - panel.index[0]).days / 365.25
    print(f"universe: {list(panel.columns)}")
    print(f"span: {panel.index[0].date()} -> {panel.index[-1].date()} "
          f"({years:.1f}y, {len(panel)} intervals)\n")

    print("— per-coin basis-aware carry (honest single-coin P&L) —")
    for c in panel.columns:
        stats_line(c, panel[c].to_numpy(),
                   extra=f" | raw funding {funding_panel[c].mean() * PPY:+6.1%}/y")

    print("\n— portfolios —")
    ew = panel.mean(axis=1)
    stats_line("hold-all equal-weight", ew.to_numpy(), "  <- zero selection bias")

    sel, picks = walk_forward_selection(
        panel, funding_panel, args.top_k, args.trail, args.rebalance,
        args.switch_bps)
    stats_line(f"walk-fwd top-{args.top_k} by trailing funding", sel.to_numpy())

    # Selection with hindsight (the WRONG way) — shown only to size the bias.
    best = panel.mean().sort_values(ascending=False).head(args.top_k).index
    stats_line(f"[biased] full-sample best {args.top_k}",
               panel[list(best)].mean(axis=1).to_numpy(),
               "  <- illustrates selection bias; NOT achievable")

    print("\n— hold-all by calendar year (regime stability) —")
    for yr, seg in ew.groupby(ew.index.year):
        if len(seg) > 60:
            stats_line(str(yr), seg.to_numpy())

    print("\nNotes: returns are per unit of ONE leg's notional; a fully-funded"
          "\nspot+margin setup earns roughly half this on total capital."
          "\nNot modeled: perp liquidation risk, counterparty risk, forgone yield.")


if __name__ == "__main__":
    main()
