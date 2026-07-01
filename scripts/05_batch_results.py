#!/usr/bin/env python3
"""
Batch runner — run the full pipeline on the top-N candidate pairs and write a
results/ folder: one report per pair plus an aggregate SUMMARY.txt.

    python scripts/05_batch_results.py            # top 10 pairs, 2y daily
    python scripts/05_batch_results.py --top 10 --days 730

Each pair gets an in-sample backtest AND an honest walk-forward (out-of-sample)
run, so the summary contrasts the optimistic vs. realistic performance.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from cryptostat.backtest import backtest_pair  # noqa: E402
from cryptostat.data import DEFAULT_UNIVERSE, fetch_ohlcv, price_panel  # noqa: E402
from cryptostat.metrics import performance_summary  # noqa: E402
from cryptostat.pairs import screen_pairs  # noqa: E402
from cryptostat.stats import engle_granger  # noqa: E402
from cryptostat.walkforward import walk_forward  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")


def _adaptive_windows(n):
    """Pick train/test sizes that yield several folds regardless of history length."""
    train = max(60, min(180, n // 4))
    test = max(20, min(45, n // 8))
    return train, test


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--days", type=int, default=730)
    ap.add_argument("--min-corr", type=float, default=0.5)
    ap.add_argument("--cost-bps", type=float, default=10.0)
    ap.add_argument("--refresh", action="store_true", help="re-download full history")
    args = ap.parse_args()

    os.makedirs(RESULTS, exist_ok=True)
    print(f"Fetching universe ({len(DEFAULT_UNIVERSE)} symbols, {args.days}d)...")
    panel = price_panel(DEFAULT_UNIVERSE, days=args.days, force_refresh=args.refresh)
    table = screen_pairs(panel, min_corr=args.min_corr)
    table.to_csv(os.path.join(RESULTS, "pairs_ranked.csv"), index=False)

    top = table.head(args.top)
    print(f"Screened {len(table)} pairs; running the top {len(top)}.\n")

    rows = []
    for i, r in top.reset_index(drop=True).iterrows():
        A, B = r["dependent"], r["independent"]
        a = fetch_ohlcv(A, days=args.days)["close"]
        b = fetch_ohlcv(B, days=args.days)["close"]
        joined = pd.concat([a.rename("a"), b.rename("b")], axis=1, join="inner").dropna()
        n = len(joined)
        if n < 120:
            print(f"  [{i+1}] {A}/{B}: only {n} overlapping days — skipped")
            continue
        train, test = _adaptive_windows(n)

        bt = backtest_pair(joined["a"], joined["b"], cost_bps=args.cost_bps)
        is_perf = performance_summary(bt.returns)
        wf = walk_forward(joined["a"], joined["b"], train=train, test=test,
                          cost_bps=args.cost_bps)
        oos_perf = wf.performance()

        rows.append({
            "pair": f"{A}/{B}", "n_days": n, "half_life": r["half_life"],
            "eg_stat": r["eg_stat"], "cointegrated": bool(r["cointegrated"]),
            "is_sharpe": is_perf.sharpe, "oos_sharpe": wf.oos_sharpe,
            "gap": is_perf.sharpe - wf.oos_sharpe, "oos_ann_return": oos_perf.ann_return,
            "oos_maxdd": oos_perf.max_drawdown, "folds": len(wf.folds),
        })
        _write_pair_report(A, B, r, bt, is_perf, wf, oos_perf, train, test)
        print(f"  [{i+1}] {A}/{B}: IS Sharpe {is_perf.sharpe:5.2f} | "
              f"OOS Sharpe {wf.oos_sharpe:5.2f} | gap {is_perf.sharpe - wf.oos_sharpe:5.2f}")

    _write_summary(rows, args)
    print(f"\nWrote {len(rows)} pair reports + SUMMARY.txt to {RESULTS}/")


def _write_pair_report(A, B, r, bt, is_perf, wf, oos_perf, train, test):
    path = os.path.join(RESULTS, f"{A}_{B}.txt".replace("/", "-"))
    with open(path, "w") as f:
        f.write(f"{'=' * 66}\n {A}  vs  {B}\n{'=' * 66}\n\n")
        f.write("COINTEGRATION (screen)\n")
        f.write(f"  correlation      {r['corr']:.4f}\n")
        f.write(f"  Engle-Granger    {r['eg_stat']:.4f}  (cointegrated={bool(r['cointegrated'])})\n")
        f.write(f"  hedge ratio beta {r['beta']:.4f}\n")
        f.write(f"  half-life        {r['half_life']:.1f} days\n\n")
        f.write("IN-SAMPLE BACKTEST (optimistic — fits and trades same data)\n")
        f.write(f"  Sharpe {is_perf.sharpe:.2f} | ann.return {is_perf.ann_return:.2%} | "
                f"maxDD {is_perf.max_drawdown:.2%} | trades {bt.n_trades}\n\n")
        f.write(f"WALK-FORWARD (honest — train {train}d / test {test}d rolling)\n")
        f.write("  " + wf.summary().replace("\n", "\n  ") + "\n\n")
        f.write("PER-FOLD OUT-OF-SAMPLE\n")
        show = wf.folds[["test_start", "test_end", "beta", "train_sharpe",
                         "test_sharpe", "n_trades"]].copy()
        show["test_start"] = pd.to_datetime(show["test_start"]).dt.date
        show["test_end"] = pd.to_datetime(show["test_end"]).dt.date
        with pd.option_context("display.float_format", lambda v: f"{v:.3f}"):
            f.write(show.to_string(index=False))
        f.write("\n")


def _write_summary(rows, args):
    df = pd.DataFrame(rows)
    path = os.path.join(RESULTS, "SUMMARY.txt")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    with open(path, "w") as f:
        f.write("CRYPTO STATISTICAL ARBITRAGE — BATCH RESULTS SUMMARY\n")
        f.write("=" * 66 + "\n")
        f.write(f"Generated : {now}\n")
        f.write(f"Universe  : {len(DEFAULT_UNIVERSE)} Coinbase USD pairs, "
                f"{args.days}d daily\n")
        f.write(f"Pairs run : {len(df)} (top candidates by cointegration)\n")
        f.write(f"Costs     : {args.cost_bps:.0f} bps per trade\n")
        f.write(f"Signal    : baseline z-score (entry 2.0 / exit 0.5)\n\n")

        f.write("METHOD\n")
        f.write("  Each pair is (1) backtested in-sample — parameters fit on the\n")
        f.write("  same data it trades, the OPTIMISTIC number — and (2) walk-forward\n")
        f.write("  validated — hedge ratio and z-score stats re-estimated on a rolling\n")
        f.write("  training window and traded only on the next unseen window, the\n")
        f.write("  HONEST number. The gap between them is the overfitting tax.\n\n")

        if len(df):
            f.write("RESULTS (sorted by out-of-sample Sharpe)\n")
            df_s = df.sort_values("oos_sharpe", ascending=False)
            cols = ["pair", "n_days", "half_life", "is_sharpe", "oos_sharpe",
                    "gap", "oos_ann_return", "oos_maxdd"]
            with pd.option_context("display.float_format", lambda v: f"{v:.3f}",
                                   "display.max_colwidth", 20):
                f.write(df_s[cols].to_string(index=False))
            f.write("\n\n")

            n_pos = int((df["oos_sharpe"] > 0).sum())
            f.write("AGGREGATE\n")
            f.write(f"  pairs with POSITIVE out-of-sample Sharpe : {n_pos} / {len(df)}\n")
            f.write(f"  mean in-sample Sharpe                    : {df['is_sharpe'].mean():.2f}\n")
            f.write(f"  mean OUT-OF-SAMPLE Sharpe                 : {df['oos_sharpe'].mean():.2f}\n")
            f.write(f"  mean overfitting gap                     : {df['gap'].mean():.2f}\n\n")

        f.write("INTERPRETATION\n")
        if len(df):
            n_pos = int((df["oos_sharpe"] > 0).sum())
            mean_oos = df["oos_sharpe"].mean()
            f.write(f"  {n_pos} of {len(df)} pairs show a POSITIVE out-of-sample Sharpe\n")
            f.write(f"  (mean OOS Sharpe {mean_oos:.2f}). Encouraging on its face — but read\n")
            f.write("  it with heavy skepticism, for two reasons:\n\n")
            f.write("  1. SELECTION BIAS. These pairs were chosen by screening the WHOLE\n")
            f.write("     history for cointegration, so the pair choice itself peeks at the\n")
            f.write("     future. Screening ~95 pairs and keeping the best 10 also invites\n")
            f.write("     multiple-testing luck. The single most important next step is to\n")
            f.write("     make pair SELECTION walk-forward too (choose pairs using only the\n")
            f.write("     training window), which typically knocks these numbers down.\n")
            f.write("  2. SMALL SAMPLE. ~2 years of daily data is a handful of folds and a\n")
            f.write("     few dozen trades per pair — wide error bars on every Sharpe here.\n\n")
        f.write("  Where in-sample beats out-of-sample, that gap is the overfitting tax;\n")
        f.write("  where OOS beats in-sample, it is usually because the walk-forward\n")
        f.write("  re-estimates the hedge ratio each window while the in-sample run holds\n")
        f.write("  one static (and drifting) beta. The unstable per-fold betas in the\n")
        f.write("  per-pair reports show how much these relationships move.\n\n")
        f.write("  Treat this as the STARTING POINT to beat, not a finished strategy. The\n")
        f.write("  research tasks in the README (walk-forward pair selection, half-life\n")
        f.write("  exits, Kalman dynamic hedge ratio, portfolio of pairs) should each be\n")
        f.write("  judged ONLY by whether they raise the out-of-sample Sharpe.\n")


if __name__ == "__main__":
    main()
