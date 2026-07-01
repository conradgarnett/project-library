"""Exotic options: closed forms vs Monte-Carlo, and structural identities."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from optlib.black_scholes import bs_price  # noqa: E402
from optlib.exotic import (  # noqa: E402
    asian_price_mc,
    barrier_price,
    barrier_price_mc,
    digital_price,
    geometric_asian_price,
    lookback_price_mc,
)

S, K, T, r, sigma, q = 100.0, 100.0, 1.0, 0.05, 0.2, 0.0


def test_digital_closed_vs_mc():
    for kind in ("call", "put"):
        cf = digital_price(S, K, T, r, sigma, q, kind, "cash", 1.0)
        rng = np.random.default_rng(1)
        Z = rng.standard_normal(2_000_000)
        ST = S * np.exp((r - q - 0.5 * sigma ** 2) * T + sigma * np.sqrt(T) * Z)
        itm = (ST > K) if kind == "call" else (ST < K)
        mc = np.exp(-r * T) * itm.mean()
        assert abs(cf - mc) < 0.005, (kind, cf, mc)


def test_digital_call_put_sum():
    # cash-or-nothing call + put = discounted 1 (one of them always pays).
    c = digital_price(S, K, T, r, sigma, q, "call")
    p = digital_price(S, K, T, r, sigma, q, "put")
    assert abs((c + p) - np.exp(-r * T)) < 1e-10


def test_geometric_asian_closed_vs_mc():
    for kind in ("call", "put"):
        cf = geometric_asian_price(S, K, T, r, sigma, q, kind)
        mc, se = asian_price_mc(S, K, T, r, sigma, q, kind, "geometric",
                                n_paths=200_000, n_steps=300, control_variate=False)
        assert abs(cf - mc) < 4 * se, (kind, cf, mc, se)


def test_arithmetic_ge_geometric():
    # AM >= GM pathwise: arithmetic-avg call >= geometric-avg call.
    ac, _ = asian_price_mc(S, K, T, r, sigma, q, "call", "arithmetic",
                           n_paths=200_000, n_steps=300)
    gc = geometric_asian_price(S, K, T, r, sigma, q, "call")
    assert ac > gc


def test_barrier_in_out_parity():
    for kind in ("call", "put"):
        vanilla = bs_price(S, K, T, r, sigma, q, kind)
        for direction, H in (("down", 90.0), ("up", 115.0)):
            ki = barrier_price(S, K, H, T, r, sigma, q, kind, direction + "-in")
            ko = barrier_price(S, K, H, T, r, sigma, q, kind, direction + "-out")
            assert abs((ki + ko) - vanilla) < 1e-8, (kind, direction, ki, ko, vanilla)


def test_barrier_closed_vs_mc():
    cf = barrier_price(S, K, 90, T, r, sigma, q, "call", "down-out")
    mc, se = barrier_price_mc(S, K, 90, T, r, sigma, q, "call", "down-out",
                              n_paths=400_000, n_steps=500)
    assert abs(cf - mc) < 4 * se, (cf, mc, se)


def test_knockout_le_vanilla():
    vanilla = bs_price(S, K, T, r, sigma, q, "call")
    ko = barrier_price(S, K, 90, T, r, sigma, q, "call", "down-out")
    assert 0 <= ko <= vanilla


def test_lookback_beats_vanilla():
    # Floating-strike lookback is worth more than the ATM vanilla.
    for kind in ("call", "put"):
        lb, se = lookback_price_mc(S, T, r, sigma, q, kind, n_paths=200_000, n_steps=300)
        assert lb > bs_price(S, S, T, r, sigma, q, kind)


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
