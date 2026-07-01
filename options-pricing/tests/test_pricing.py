"""
Correctness tests for optlib.

Run with:  python -m pytest -q     (from the options-pricing/ directory)
or:        python tests/test_pricing.py   (no pytest needed — has a fallback)

Validation strategy
--------------------
* Prices are checked against textbook reference values.
* Greeks are checked against independent central finite differences of the
  price function (analytic Greek must match the numerical derivative).
* Put-call parity must hold to machine precision.
* Implied vol must round-trip (price -> iv -> price).
* Monte-Carlo price must land within a few standard errors of Black-Scholes.
"""

from __future__ import annotations

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optlib.black_scholes import (  # noqa: E402
    bs_greeks,
    bs_price,
    implied_volatility,
    put_call_parity_gap,
)
from optlib.monte_carlo import MonteCarloPricer  # noqa: E402


# --------------------------------------------------------------------------- #
def test_reference_price():
    # Classic Hull example: S=K=100, T=1, r=5%, sigma=20%, q=0.
    c = bs_price(100, 100, 1, 0.05, 0.2, 0.0, "call")
    p = bs_price(100, 100, 1, 0.05, 0.2, 0.0, "put")
    assert abs(c - 10.4506) < 1e-3, c
    assert abs(p - 5.5735) < 1e-3, p


def test_put_call_parity():
    for S, K, T, r, sigma, q in [
        (100, 100, 1, 0.05, 0.2, 0.0),
        (95, 110, 0.5, 0.03, 0.35, 0.02),
        (120, 100, 2.0, 0.01, 0.15, 0.05),
    ]:
        c = bs_price(S, K, T, r, sigma, q, "call")
        p = bs_price(S, K, T, r, sigma, q, "put")
        assert abs(put_call_parity_gap(c, p, S, K, T, r, q)) < 1e-9


def test_greeks_match_finite_difference():
    S, K, T, r, sigma, q = 100, 105, 0.75, 0.04, 0.28, 0.01
    for kind in ("call", "put"):
        g = bs_greeks(S, K, T, r, sigma, q, kind)

        h = 1e-4 * S
        d_num = (bs_price(S + h, K, T, r, sigma, q, kind)
                 - bs_price(S - h, K, T, r, sigma, q, kind)) / (2 * h)
        assert abs(g.delta - d_num) < 1e-4, (kind, g.delta, d_num)

        gamma_num = (bs_price(S + h, K, T, r, sigma, q, kind)
                     - 2 * bs_price(S, K, T, r, sigma, q, kind)
                     + bs_price(S - h, K, T, r, sigma, q, kind)) / h ** 2
        assert abs(g.gamma - gamma_num) < 1e-3, (kind, g.gamma, gamma_num)

        hv = 1e-5
        vega_num = (bs_price(S, K, T, r, sigma + hv, q, kind)
                    - bs_price(S, K, T, r, sigma - hv, q, kind)) / (2 * hv)
        assert abs(g.vega - vega_num) < 1e-2, (kind, g.vega, vega_num)

        hr = 1e-6
        rho_num = (bs_price(S, K, T, r + hr, sigma, q, kind)
                   - bs_price(S, K, T, r - hr, sigma, q, kind)) / (2 * hr)
        assert abs(g.rho - rho_num) < 1e-2, (kind, g.rho, rho_num)

        # Theta = -dV/dT.
        ht = 1e-6
        theta_num = -(bs_price(S, K, T + ht, r, sigma, q, kind)
                      - bs_price(S, K, T - ht, r, sigma, q, kind)) / (2 * ht)
        assert abs(g.theta - theta_num) < 1e-2, (kind, g.theta, theta_num)


def test_gamma_vega_call_put_equal():
    args = (100, 100, 1.0, 0.05, 0.2, 0.0)
    gc = bs_greeks(*args, "call")
    gp = bs_greeks(*args, "put")
    assert abs(gc.gamma - gp.gamma) < 1e-12
    assert abs(gc.vega - gp.vega) < 1e-12


def test_delta_bounds():
    c = bs_greeks(100, 100, 1, 0.05, 0.2, 0.0, "call")
    p = bs_greeks(100, 100, 1, 0.05, 0.2, 0.0, "put")
    assert 0.0 <= c.delta <= 1.0
    assert -1.0 <= p.delta <= 0.0


def test_implied_vol_roundtrip():
    S, K, T, r, q = 100, 110, 0.5, 0.03, 0.01
    for true_sig in (0.1, 0.25, 0.6):
        for kind in ("call", "put"):
            price = bs_price(S, K, T, r, true_sig, q, kind)
            iv = implied_volatility(price, S, K, T, r, q, kind)
            assert abs(iv - true_sig) < 1e-5, (kind, true_sig, iv)


def test_expiry_intrinsic():
    # At T=0 the option is worth its intrinsic value.
    assert abs(bs_price(120, 100, 0.0, 0.05, 0.2, 0.0, "call") - 20.0) < 1e-9
    assert abs(bs_price(80, 100, 0.0, 0.05, 0.2, 0.0, "put") - 20.0) < 1e-9
    assert bs_price(80, 100, 0.0, 0.05, 0.2, 0.0, "call") == 0.0


def test_monte_carlo_within_ci():
    S, K, T, r, sigma, q = 100, 105, 0.75, 0.045, 0.28, 0.01
    mc = MonteCarloPricer(n_paths=1_000_000, seed=123)
    for kind in ("call", "put"):
        truth = bs_price(S, K, T, r, sigma, q, kind)
        res = mc.price(S, K, T, r, sigma, q, kind)
        # Within 4 standard errors is an extremely safe bound.
        assert abs(res.price - truth) < 4 * res.std_error, (kind, res, truth)


def test_monte_carlo_greeks_close():
    S, K, T, r, sigma, q = 100, 100, 1.0, 0.05, 0.2, 0.0
    analytic = bs_greeks(S, K, T, r, sigma, q, "call")
    mc = MonteCarloPricer(n_paths=1_000_000, seed=7).greeks(S, K, T, r, sigma, q, "call")
    assert abs(mc["delta"] - analytic.delta) < 0.02
    assert abs(mc["vega"] - analytic.vega) < 1.0
    assert abs(mc["price"] - analytic.price) < 0.05


# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    # Minimal fallback runner so the file works without pytest installed.
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failures}/{len(fns)} passed")
    sys.exit(1 if failures else 0)
