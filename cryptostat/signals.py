"""
Trading signals: turn a spread's z-score into a position.

This module is deliberately the *thin* part of the project — it holds the
baseline signal so the pipeline runs end-to-end, and it is the main place YOU
are meant to do research. The plumbing around it (data, cointegration, the
backtest engine, metrics) is solid; the edge lives here.

Baseline: a symmetric z-score band. Go long the spread when it is cheap
(z below -entry), short when rich (z above +entry), flat when it reverts inside
±exit, and bail if it diverges past ±stop.

    position = zscore_signal(z, entry=2.0, exit=0.5, stop=4.0)
"""

from __future__ import annotations

import numpy as np


def zscore_signal(z, entry=2.0, exit=0.5, stop=None):
    """
    Stateful position on the spread from its z-score.

    Returns an array in {-1, 0, +1}: +1 = long the spread (long leg A / short
    β·leg B), -1 = short the spread, 0 = flat. ``exit`` is the reversion band
    that closes a position; ``stop`` (optional) closes it if the spread instead
    keeps diverging (a simple risk stop).
    """
    z = np.asarray(z, dtype=float)
    pos = np.zeros(z.size)
    state = 0
    for t in range(z.size):
        zt = z[t]
        if np.isnan(zt):
            pos[t] = state
            continue
        if state == 0:
            if zt <= -entry:
                state = 1
            elif zt >= entry:
                state = -1
        elif state == 1:                       # long spread, waiting to revert up
            if zt >= -exit or (stop is not None and zt <= -stop):
                state = 0
        elif state == -1:                      # short spread, waiting to revert down
            if zt <= exit or (stop is not None and zt >= stop):
                state = 0
        pos[t] = state
    return pos


# --------------------------------------------------------------------------- #
# ▼▼▼  YOUR RESEARCH GOES HERE  ▼▼▼
#
# The baseline above is intentionally naive. Ideas that are known to matter and
# are worth testing (each is a mini-experiment: implement, backtest, compare
# out-of-sample, keep only what survives):
#
#   * Half-life-aware sizing/holding: scale the z-window and max holding period
#     to each pair's estimated mean-reversion half-life instead of a fixed band.
#   * Dynamic hedge ratio: replace the static OLS beta with a Kalman filter so
#     the spread tracks a slowly-drifting relationship (see cryptostat.stats
#     for the static version to extend).
#   * Volatility-scaled positions: size inversely to recent spread volatility so
#     risk is constant across regimes.
#   * Entry/exit asymmetry and time-stops: exit if the spread hasn't reverted
#     within ~N half-lives even if z is still extreme (mean reversion broke).
#   * Regime / cointegration re-check: periodically re-test the pair and stand
#     down when the relationship decays (rolling Engle-Granger p-value filter).
#   * Portfolio of pairs: allocate across many pairs with a risk budget rather
#     than trading one at a time.
#
# Implement these as new functions returning a position array, then compare them
# in scripts/03_backtest_pair.py against the baseline.
# --------------------------------------------------------------------------- #
