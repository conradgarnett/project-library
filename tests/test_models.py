"""Alternative models: Merton closed-vs-MC, BS limits, and smile generation."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optlib.black_scholes import bs_price, implied_volatility  # noqa: E402
from optlib.models import (  # noqa: E402
    heston_price_mc,
    merton_jump_price,
    merton_jump_price_mc,
)

S, K, T, r, sigma, q = 100.0, 100.0, 1.0, 0.05, 0.2, 0.0


def test_merton_closed_vs_mc():
    for kind in ("call", "put"):
        cf = merton_jump_price(S, K, T, r, sigma, q, kind, lam=1.0, muJ=-0.1, sigJ=0.15)
        mc, se = merton_jump_price_mc(S, K, T, r, sigma, q, kind, lam=1.0,
                                      muJ=-0.1, sigJ=0.15, n_paths=1_000_000)
        assert abs(cf - mc) < 4 * se, (kind, cf, mc, se)


def test_merton_reduces_to_bs_without_jumps():
    for kind in ("call", "put"):
        cf = merton_jump_price(S, K, T, r, sigma, q, kind, lam=0.0)
        assert abs(cf - bs_price(S, K, T, r, sigma, q, kind)) < 1e-8


def test_merton_generates_skew():
    ivs = []
    for Kx in (85, 100, 115):
        p = merton_jump_price(S, Kx, T, r, sigma, q, "call", lam=1.0, muJ=-0.1, sigJ=0.15)
        ivs.append(implied_volatility(p, S, Kx, T, r, q, "call"))
    # Negative-mean jumps => downward-sloping skew and IVs above the base sigma.
    assert ivs[0] > ivs[2]
    assert all(iv > sigma for iv in ivs)


def test_heston_reduces_to_bs():
    bs = bs_price(100, 100, 1.0, 0.05, 0.2, 0.0, "call")
    mc, se = heston_price_mc(100, 100, 1.0, 0.05, 0.0, "call", v0=0.04, kappa=2.0,
                             theta=0.04, xi=1e-6, rho=0.0, n_paths=400_000, n_steps=200)
    assert abs(bs - mc) < 4 * se, (bs, mc, se)


def test_heston_negative_rho_makes_skew():
    ivs = []
    for Kx in (85, 100, 115):
        p, _ = heston_price_mc(100, Kx, 1.0, 0.05, 0.0, "call", v0=0.04, kappa=2.0,
                               theta=0.04, xi=0.5, rho=-0.7, n_paths=400_000, n_steps=200)
        ivs.append(implied_volatility(p, 100, Kx, 1.0, 0.05, 0.0, "call"))
    assert ivs[0] > ivs[1] > ivs[2]  # monotone equity skew


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
