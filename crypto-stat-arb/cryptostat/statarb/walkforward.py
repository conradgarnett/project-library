"""
Walk-forward (out-of-sample) validation for pairs trading.

This is the harness that keeps you honest. The plain backtest in
``cryptostat.backtest`` fits the hedge ratio and z-score statistics on the whole
history, then "trades" that same history — so it has seen the future. Any
strategy looks good that way.

Walk-forward instead re-estimates the parameters on a **training window** and
trades only the **next, unseen window**, rolling forward through time. The
concatenated out-of-sample returns are what a strategy would actually have
earned. If in-sample looks great but out-of-sample doesn't, you were overfitting
— and that gap is the single most important number in the whole project.

    from cryptostat.walkforward import walk_forward
    wf = walk_forward(panel["BCH-USD"], panel["LTC-USD"], train=180, test=30)
    print(wf.summary())
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..common.metrics import performance_summary, sharpe
from .signals import zscore_signal
from ..common.stats import engle_granger, hedge_ratio


@dataclass
class WalkForwardResult:
    oos_returns: pd.Series       # concatenated out-of-sample returns
    folds: pd.DataFrame          # per-fold diagnostics
    insample_sharpe: float       # naive full-sample-fit Sharpe (the optimistic one)
    oos_sharpe: float            # honest out-of-sample Sharpe
    periods_per_year: int

    def performance(self):
        return performance_summary(self.oos_returns, self.periods_per_year)

    def summary(self) -> str:
        p = self.performance()
        gap = self.insample_sharpe - self.oos_sharpe
        return (
            f"Walk-forward: {len(self.folds)} folds, {p.n_periods} OOS periods\n"
            f"  in-sample Sharpe (optimistic) : {self.insample_sharpe:6.2f}\n"
            f"  OUT-OF-SAMPLE Sharpe (honest)  : {self.oos_sharpe:6.2f}\n"
            f"  overfitting gap                : {gap:6.2f}\n"
            f"  OOS ann.return {p.ann_return:6.2%} | maxDD {p.max_drawdown:6.2%} | "
            f"hit {p.hit_rate:5.1%}"
        )


def _spread_returns(a, b, beta, pos):
    """P&L of a dollar-neutral spread position, as a return on gross notional."""
    spread = a - beta * b
    dspread = np.diff(spread, prepend=spread[0])
    gross = np.abs(a) + np.abs(beta) * np.abs(b)
    pos_lag = np.concatenate([[0.0], pos[:-1]])
    pnl = pos_lag * dspread
    return np.divide(pnl, gross, out=np.zeros_like(pnl), where=gross > 0)


def walk_forward(
    price_a, price_b, train=180, test=30, anchored=False,
    entry=2.0, exit=0.5, stop=None, cost_bps=10.0,
    hedge_method="ols", recheck_coint=False, coint_alpha=0.05,
    signal_fn=None, periods_per_year=365,
) -> WalkForwardResult:
    """
    Roll a train→test window through the history and collect out-of-sample returns.

    Parameters
    ----------
    train : length of the estimation (in-sample) window, in periods.
    test  : length of each out-of-sample window, in periods.
    anchored : if True the training window expands from the start (anchored
        walk-forward); if False it is a fixed-length rolling window.
    recheck_coint : if True, re-test cointegration on each training window and
        **stand down** (stay flat) in test windows where the pair is no longer
        cointegrated — a realistic "the relationship broke" guard.
    signal_fn : callable(z_array)->positions; defaults to the baseline z-score.

    Frozen parameters: within each test window the hedge ratio β and the
    z-score mean/std are those estimated on the *preceding* training window
    only — nothing from the test window leaks into them.
    """
    a_full = np.asarray(price_a, dtype=float)
    b_full = np.asarray(price_b, dtype=float)
    idx = price_a.index if isinstance(price_a, pd.Series) else pd.RangeIndex(len(a_full))
    n = a_full.size
    if signal_fn is None:
        signal_fn = lambda z: zscore_signal(z, entry=entry, exit=exit, stop=stop)  # noqa: E731

    oos_ret = np.full(n, np.nan)
    fold_rows = []

    t = train
    while t + test <= n:
        tr = slice(0 if anchored else t - train, t)
        te = slice(t, t + test)
        a_tr, b_tr = a_full[tr], b_full[tr]
        a_te, b_te = a_full[te], b_full[te]

        beta = hedge_ratio(a_tr, b_tr, method=hedge_method)
        spread_tr = a_tr - beta * b_tr
        mu, sd = spread_tr.mean(), spread_tr.std()

        stood_down = False
        if recheck_coint and not engle_granger(a_tr, b_tr).is_cointegrated(coint_alpha):
            stood_down = True
            pos_te = np.zeros(a_te.size)
            ret_te = np.zeros(a_te.size)
        else:
            z_te = (a_te - beta * b_te - mu) / sd if sd > 0 else np.zeros(a_te.size)
            pos_te = np.asarray(signal_fn(z_te), dtype=float)
            ret_te = _spread_returns(a_te, b_te, beta, pos_te)
            dpos = np.abs(np.diff(pos_te, prepend=0.0))
            ret_te = ret_te - dpos * (cost_bps / 1e4)

        oos_ret[te] = ret_te

        # In-sample (train) return for the overfitting diagnostic.
        z_tr = (spread_tr - mu) / sd if sd > 0 else np.zeros(a_tr.size)
        pos_tr = np.asarray(signal_fn(z_tr), dtype=float)
        ret_tr = _spread_returns(a_tr, b_tr, beta, pos_tr)

        fold_rows.append({
            "train_start": idx[tr.start], "test_start": idx[t],
            "test_end": idx[min(t + test, n) - 1],
            "beta": beta, "train_sharpe": sharpe(ret_tr, periods_per_year),
            "test_sharpe": sharpe(ret_te, periods_per_year),
            "n_trades": int((np.abs(np.diff(pos_te, prepend=0.0)) > 0).sum()),
            "stood_down": stood_down,
        })
        t += test

    oos = pd.Series(oos_ret, index=idx).dropna()
    folds = pd.DataFrame(fold_rows)

    # Naive full-sample-fit Sharpe (the optimistic number to beat).
    beta_full = hedge_ratio(a_full, b_full, method=hedge_method)
    spread_full = a_full - beta_full * b_full
    z_full = (spread_full - spread_full.mean()) / spread_full.std()
    ret_full = _spread_returns(a_full, b_full, beta_full,
                               np.asarray(signal_fn(z_full), dtype=float))
    insample = sharpe(ret_full, periods_per_year)

    return WalkForwardResult(
        oos_returns=oos, folds=folds, insample_sharpe=float(insample),
        oos_sharpe=float(sharpe(oos, periods_per_year)),
        periods_per_year=periods_per_year,
    )
