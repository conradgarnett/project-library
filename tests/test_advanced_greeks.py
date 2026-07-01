"""
Validate every higher-order Greek against an independent finite difference of
the analytic price / first-order Greeks. Run:

    python tests/test_advanced_greeks.py      (or: python -m pytest -q)
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from optlib.black_scholes import bs_greeks, bs_price  # noqa: E402
from optlib.greeks_advanced import advanced_greeks  # noqa: E402

S, K, T, r, sigma, q = 100.0, 105.0, 0.75, 0.04, 0.28, 0.01


def _price(**kw):
    args = dict(S=S, K=K, T=T, r=r, sigma=sigma, q=q)
    args.update(kw)
    return float(bs_price(args["S"], args["K"], args["T"], args["r"],
                          args["sigma"], args["q"], kw.get("kind", "call")))


def _delta(kind, **kw):
    args = dict(S=S, K=K, T=T, r=r, sigma=sigma, q=q)
    args.update(kw)
    return bs_greeks(args["S"], args["K"], args["T"], args["r"],
                     args["sigma"], args["q"], kind).delta


def _vega(kind, **kw):
    args = dict(S=S, K=K, T=T, r=r, sigma=sigma, q=q)
    args.update(kw)
    return bs_greeks(args["S"], args["K"], args["T"], args["r"],
                     args["sigma"], args["q"], kind).vega


def _gamma(kind, **kw):
    args = dict(S=S, K=K, T=T, r=r, sigma=sigma, q=q)
    args.update(kw)
    return bs_greeks(args["S"], args["K"], args["T"], args["r"],
                     args["sigma"], args["q"], kind).gamma


def _check(name, analytic, numeric, tol):
    assert abs(analytic - numeric) < tol, f"{name}: analytic={analytic:.6g} fd={numeric:.6g}"


def test_advanced_greeks_vs_finite_difference():
    for kind in ("call", "put"):
        g = advanced_greeks(S, K, T, r, sigma, q, kind)

        hS, hv, hT, hK = 1e-2, 1e-4, 1e-4, 1e-2

        # vanna = ∂delta/∂sigma
        vanna_fd = (_delta(kind, sigma=sigma + hv) - _delta(kind, sigma=sigma - hv)) / (2 * hv)
        _check("vanna", g.vanna, vanna_fd, 1e-3)

        # charm = ∂delta/∂T
        charm_fd = (_delta(kind, T=T + hT) - _delta(kind, T=T - hT)) / (2 * hT)
        _check("charm", g.charm, charm_fd, 1e-3)

        # vomma = ∂vega/∂sigma
        vomma_fd = (_vega(kind, sigma=sigma + hv) - _vega(kind, sigma=sigma - hv)) / (2 * hv)
        _check("vomma", g.vomma, vomma_fd, 1e-1)

        # veta = ∂vega/∂T
        veta_fd = (_vega(kind, T=T + hT) - _vega(kind, T=T - hT)) / (2 * hT)
        _check("veta", g.veta, veta_fd, 1e-1)

        # speed = ∂gamma/∂S
        speed_fd = (_gamma(kind, S=S + hS) - _gamma(kind, S=S - hS)) / (2 * hS)
        _check("speed", g.speed, speed_fd, 1e-5)

        # zomma = ∂gamma/∂sigma
        zomma_fd = (_gamma(kind, sigma=sigma + hv) - _gamma(kind, sigma=sigma - hv)) / (2 * hv)
        _check("zomma", g.zomma, zomma_fd, 1e-3)

        # color = ∂gamma/∂T
        color_fd = (_gamma(kind, T=T + hT) - _gamma(kind, T=T - hT)) / (2 * hT)
        _check("color", g.color, color_fd, 1e-3)

        # dual_delta = ∂V/∂K
        dd_fd = (_price(K=K + hK, kind=kind) - _price(K=K - hK, kind=kind)) / (2 * hK)
        _check("dual_delta", g.dual_delta, dd_fd, 1e-3)

        # dual_gamma = ∂²V/∂K²
        dg_fd = (_price(K=K + hK, kind=kind) - 2 * _price(kind=kind)
                 + _price(K=K - hK, kind=kind)) / hK ** 2
        _check("dual_gamma", g.dual_gamma, dg_fd, 1e-3)

        # ultima = ∂³V/∂sigma³ (4-point central third derivative)
        h = 5e-3
        ultima_fd = (_price(sigma=sigma + 2 * h, kind=kind)
                     - 2 * _price(sigma=sigma + h, kind=kind)
                     + 2 * _price(sigma=sigma - h, kind=kind)
                     - _price(sigma=sigma - 2 * h, kind=kind)) / (2 * h ** 3)
        _check("ultima", g.ultima, ultima_fd, 5.0)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failures = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failures += 1
            print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - failures}/{len(fns)} passed")
    sys.exit(1 if failures else 0)
