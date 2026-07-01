"""Implied vs realized: probabilities, density recovery, and the hedging link."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from optlib.greeks_advanced import advanced_greeks  # noqa: E402
from optlib.implied import (  # noqa: E402
    breakeven_move,
    delta_hedge_pnl,
    implied_density_from_model,
    implied_prob_itm,
    realized_volatility,
    variance_risk_premium,
)


def test_realized_vol_recovers_true():
    rng = np.random.default_rng(0)
    n, dt, true = 5040, 1 / 252, 0.30
    rets = (0.05 - 0.5 * true ** 2) * dt + true * np.sqrt(dt) * rng.standard_normal(n)
    px = 100 * np.exp(np.cumsum(rets))
    assert abs(realized_volatility(px) - true) < 0.02


def test_implied_prob_equals_dual_delta():
    S, K, T, r, sigma, q = 100, 105, 0.5, 0.04, 0.25, 0.0
    p = implied_prob_itm(S, K, T, r, sigma, q, "call")
    dd = advanced_greeks(S, K, T, r, sigma, q, "call").dual_delta
    assert abs(p - (-np.exp(r * T) * dd)) < 1e-9


def test_real_world_vs_risk_neutral_prob():
    S, K, T, r, sigma, q = 100, 105, 0.5, 0.04, 0.25, 0.0
    rn = implied_prob_itm(S, K, T, r, sigma, q, "call", "risk-neutral")
    rw = implied_prob_itm(S, K, T, r, sigma, q, "call", "real-world", mu=0.10)
    # Higher physical drift => higher real-world ITM probability.
    assert rw > rn


def test_breeden_litzenberger_density():
    mids, dens = implied_density_from_model(100, 100, 1.0, 0.03, 0.25, 0.0, width=0.95, n=501)
    area = np.trapezoid(dens, mids)
    assert abs(area - 1.0) < 0.02, area
    assert (dens >= 0).all()


def test_breakeven_move_formula():
    assert abs(breakeven_move(100, 0.25) - 100 * 0.25 / np.sqrt(252)) < 1e-12


def test_delta_hedge_pnl_tracks_realized_vs_implied():
    # Long option: profit iff realized variance > implied variance, and the
    # simulated P&L matches the gamma-theta prediction.
    hi = delta_hedge_pnl(100, 100, 0.5, 0.03, 0.20, 0.30, kind="call",
                         position="long", n_steps=126, n_paths=40_000)
    lo = delta_hedge_pnl(100, 100, 0.5, 0.03, 0.20, 0.10, kind="call",
                         position="long", n_steps=126, n_paths=40_000)
    assert hi["mean_pnl"] > 0 and lo["mean_pnl"] < 0
    assert abs(hi["mean_pnl"] - hi["predicted_pnl"]) < 3 * hi["std_error"] + 0.02
    # Short option is the mirror image.
    sh = delta_hedge_pnl(100, 100, 0.5, 0.03, 0.20, 0.30, kind="call",
                         position="short", n_steps=126, n_paths=40_000)
    assert sh["mean_pnl"] < 0


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for fn in fns:
        try:
            fn(); print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            fails += 1; print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
