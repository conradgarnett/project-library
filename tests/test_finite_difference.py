"""Crank-Nicolson PDE pricer: convergence to BS and American premium."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optlib.black_scholes import bs_greeks, bs_price  # noqa: E402
from optlib.binomial import binomial_price  # noqa: E402
from optlib.finite_difference import crank_nicolson  # noqa: E402


def test_cn_matches_black_scholes():
    S, K, T, r, sigma, q = 100, 105, 0.75, 0.045, 0.28, 0.01
    for kind in ("call", "put"):
        bs = bs_price(S, K, T, r, sigma, q, kind)
        res = crank_nicolson(S, K, T, r, sigma, q, kind, "european",
                             n_space=500, n_time=500)
        assert abs(res.price - bs) < 0.01, (kind, res.price, bs)


def test_cn_greeks_match():
    S, K, T, r, sigma, q = 100, 105, 0.75, 0.045, 0.28, 0.01
    g = bs_greeks(S, K, T, r, sigma, q, "call")
    res = crank_nicolson(S, K, T, r, sigma, q, "call", "european",
                         n_space=600, n_time=600)
    assert abs(res.delta - g.delta) < 5e-3
    assert abs(res.gamma - g.gamma) < 5e-4


def test_cn_american_matches_tree():
    S, K, T, r, sigma, q = 100, 110, 1.0, 0.06, 0.3, 0.0
    cn = crank_nicolson(S, K, T, r, sigma, q, "put", "american",
                        n_space=600, n_time=600).price
    tree = binomial_price(S, K, T, r, sigma, q, "put", "american", 1500)
    assert abs(cn - tree) < 0.03, (cn, tree)
    euro = crank_nicolson(S, K, T, r, sigma, q, "put", "european",
                          n_space=600, n_time=600).price
    assert cn > euro + 1e-2  # positive early-exercise premium


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
