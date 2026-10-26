#!/usr/bin/env python3
"""
Local replay backtest of the QuantConnect strategy on REAL exchange data.

Drives the exact components the QC algorithm runs — screen_pairs (walk-forward
pair selection), PairEngine (hedge, ML signal, time stops), inverse_risk_budgets
and RiskManager — through real Coinbase daily closes from the research repo's
data cache. The event loop mirrors main.py bar for bar:

    at close t-1   weights were set                     (QC: OnData yesterday)
    close t-1 -> t portfolio earns those weights        (QC: holdings P&L)
    month rolled?  rebuild on bars [t-train, t)         (QC: Train at midnight)
    at close t     engines consume bar t -> new weights (QC: OnData today)
    weight change  costs fee_bps on traded notional     (QC: brokerage fees)

What this does NOT capture vs. a QC run: intraday paths, funding payments on
perps, margin mechanics, and exchange-specific fee schedules — which is why the
default fee (10 bps per side) is deliberately on the punitive side for majors.

    python quantconnect/backtest_local.py                 # lstm, whole history
    python quantconnect/backtest_local.py --kind zscore   # the control group
    python quantconnect/backtest_local.py --kind all      # zscore/ridge/gbm/lstm
    python quantconnect/backtest_local.py --hedge kalman --verbose
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                                   # spread_ml
sys.path.insert(0, os.path.dirname(HERE))                  # cryptostat (data layer)

from cryptostat.common.data import fetch_ohlcv  # noqa: E402
from spread_ml import (  # noqa: E402
    PairConfig, PairEngine, RiskManager,
    annualized_return, annualized_vol, hit_rate, inverse_risk_budgets,
    max_drawdown, screen_pairs, sharpe,
)

# Spot mirror of the QC perp universe (MATIC excluded: delisted 2025-10).
UNIVERSE = [
    "BTC-USD", "ETH-USD", "SOL-USD", "AVAX-USD", "ADA-USD", "DOT-USD",
    "LINK-USD", "LTC-USD", "BCH-USD", "ETC-USD", "XLM-USD", "ATOM-USD",
    "ALGO-USD", "XTZ-USD", "UNI-USD", "AAVE-USD", "FIL-USD",
]


def load_panel(days):
    cols = {}
    for s in UNIVERSE:
        try:
            cols[s] = fetch_ohlcv(s, days=days)["close"]
        except Exception as err:
            print(f"  skipping {s}: {err}")
    panel = pd.DataFrame(cols).dropna()
    return panel


def run(panel, kind="lstm", hedge="ols", train=250, max_pairs=4,
        gross_target=0.90, fee_bps=10.0, target_vol=0.15, max_dd=0.20,
        halt_bars=30, time_stop_hl=3.0, seed=0, verbose=False):
    """One full replay. Returns (stats dict, equity Series, engines dict)."""
    dates = panel.index
    names = list(panel.columns)
    px = panel.to_numpy(dtype=float)
    n = len(panel)

    cfg = dict(kind=kind, hedge=hedge, time_stop_half_lives=time_stop_hl, seed=seed)
    engines, pair_cols = {}, {}
    risk = RiskManager(target_vol=target_vol, max_drawdown=max_dd,
                       halt_bars=halt_bars, periods_per_year=365)
    w = np.zeros(len(names))               # weights held into the next bar
    equity = 1.0
    eq_curve = np.empty(n - train)
    fees_paid = 0.0
    rebuild_month = None
    n_rebuilds = 0

    for t in range(train, n):
        # --- 1. earn yesterday's weights over the close-to-close move -------- #
        r_assets = px[t] / px[t - 1] - 1.0
        equity *= 1.0 + float(w @ r_assets)

        # --- 2. monthly rebuild on the trailing training window only --------- #
        if dates[t].month != rebuild_month:
            rebuild_month = dates[t].month
            n_rebuilds += 1
            window = panel.iloc[t - train:t]
            closes = {c: window[c].to_numpy(dtype=float) for c in names}
            table = screen_pairs(closes)
            selected, used = [], set()
            for row in table:
                if len(selected) >= max_pairs:
                    break
                if not row["candidate"] or row["a"] in used or row["b"] in used:
                    continue
                selected.append(row)
                used.update((row["a"], row["b"]))
            new_engines = {}
            for row in selected:
                name = f"{row['a']}|{row['b']}"
                eng = engines.get(name) or PairEngine(name, PairConfig(**cfg))
                if eng.fit(closes[row["a"]], closes[row["b"]]):
                    new_engines[name] = eng
                    pair_cols[name] = (names.index(row["a"]), names.index(row["b"]))
            engines = new_engines
            if verbose:
                print(f"  {dates[t].date()} rebuild #{n_rebuilds}: "
                      f"{[k for k in engines] or 'NO PAIRS (flat)'}")

        # --- 3. feed engines today's bar; risk; new weights ------------------- #
        event = risk.update(equity)
        if verbose and event:
            print(f"  {dates[t].date()} risk: {event} (dd {risk.drawdown:+.1%})")
        w_new = np.zeros(len(names))
        if not risk.halted and engines:
            budgets = inverse_risk_budgets(
                list(engines.values()), gross_target * risk.exposure_scale())
            for name, eng in engines.items():
                ia, ib = pair_cols[name]
                eng.on_bar(px[t, ia], px[t, ib])
                wa, wb = eng.leg_weights(px[t, ia], px[t, ib], budgets.get(name, 0.0))
                w_new[ia] += wa
                w_new[ib] += wb

        # --- 4. fees on turnover (both sides, like QC's taker fills) ---------- #
        turnover = float(np.abs(w_new - w).sum())
        fee = turnover * fee_bps / 1e4
        fees_paid += fee * equity
        equity *= 1.0 - fee
        w = w_new
        eq_curve[t - train] = equity

    eq = pd.Series(eq_curve, index=dates[train:])
    rets = eq.pct_change().dropna().to_numpy()
    stats = {
        "kind": kind, "hedge": hedge,
        "total_return": float(eq.iloc[-1] - 1.0),
        "ann_return": annualized_return(rets),
        "ann_vol": annualized_vol(rets),
        "sharpe": sharpe(rets),
        "max_dd": max_drawdown(eq.to_numpy()),
        "hit_rate": hit_rate(rets),
        "fees_paid_pct": fees_paid,                # in units of start equity
        "rebuilds": n_rebuilds,
        "bars": len(eq),
        "kill_switches": sum("KILL" in e for e in risk.events),
    }
    return stats, eq, engines


def _print_stats(s):
    print(f"  {s['kind']:7s} {s['hedge']:7s} | total {s['total_return']:+8.1%} | "
          f"ann {s['ann_return']:+7.1%} | vol {s['ann_vol']:6.1%} | "
          f"Sharpe {s['sharpe']:5.2f} | maxDD {s['max_dd']:7.1%} | "
          f"hit {s['hit_rate']:5.1%} | fees {s['fees_paid_pct']:5.1%} | "
          f"kills {s['kill_switches']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", default="lstm",
                    choices=["lstm", "gbm", "ridge", "zscore", "all"])
    ap.add_argument("--hedge", default="ols", choices=["ols", "tls", "kalman"])
    ap.add_argument("--days", type=int, default=1500)
    ap.add_argument("--train", type=int, default=250)
    ap.add_argument("--max-pairs", type=int, default=4)
    ap.add_argument("--fee-bps", type=float, default=10.0)
    ap.add_argument("--gross", type=float, default=0.90)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--save", help="write the equity curve CSV here")
    args = ap.parse_args()

    panel = load_panel(args.days)
    print(f"panel: {panel.shape[0]} days x {panel.shape[1]} symbols "
          f"({panel.index.min().date()} -> {panel.index.max().date()})")
    oos_start = panel.index[args.train].date()
    print(f"walk-forward: first {args.train} days are warm-up; "
          f"P&L starts {oos_start} (every decision uses trailing data only)\n")

    kinds = ["zscore", "ridge", "gbm", "lstm"] if args.kind == "all" else [args.kind]
    results = {}
    for kind in kinds:
        t0 = time.time()
        stats, eq, engines = run(
            panel, kind=kind, hedge=args.hedge, train=args.train,
            max_pairs=args.max_pairs, gross_target=args.gross,
            fee_bps=args.fee_bps, seed=args.seed, verbose=args.verbose)
        results[kind] = (stats, eq, engines)
        _print_stats(stats)
        if args.verbose:
            for name, eng in engines.items():
                print(f"    final book {name}: pos {eng.position:+d} "
                      f"paper {eng.paper_pnl:+.2%}")
        print(f"    ({stats['rebuilds']} rebuilds, {stats['bars']} bars, "
              f"{time.time() - t0:.0f}s)\n")

    if args.save:
        pd.DataFrame({k: v[1] for k, v in results.items()}).to_csv(args.save)
        print(f"equity curves -> {args.save}")


if __name__ == "__main__":
    main()
