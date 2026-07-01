#!/usr/bin/env python3
"""
Command-line options pricing & Greeks calculator.

Examples
--------
Price a call and show all Greeks + a Monte-Carlo cross-check:

    python cli.py --S 100 --K 105 --T 0.5 --r 0.05 --sigma 0.25 --kind call

Back out implied vol from an observed price:

    python cli.py --S 100 --K 100 --T 1 --r 0.05 --kind call --implied-from 10.45

Skip the Monte-Carlo comparison (analytic only):

    python cli.py --S 100 --K 100 --T 1 --r 0.05 --sigma 0.2 --no-mc
"""

from __future__ import annotations

import argparse
import sys

from optlib.black_scholes import bs_greeks, implied_volatility, put_call_parity_gap, bs_price
from optlib.compare import compare_greeks, compare_prices


def _fmt(x, w=12, p=4):
    return f"{x:>{w}.{p}f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Black-Scholes + Monte-Carlo options pricing & Greeks calculator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    ap.add_argument("--S", type=float, required=True, help="spot price")
    ap.add_argument("--K", type=float, required=True, help="strike price")
    ap.add_argument("--T", type=float, required=True, help="time to expiry (years)")
    ap.add_argument("--r", type=float, required=True, help="risk-free rate (e.g. 0.05)")
    ap.add_argument("--sigma", type=float, help="volatility (e.g. 0.2). Omit with --implied-from")
    ap.add_argument("--q", type=float, default=0.0, help="dividend yield")
    ap.add_argument("--kind", choices=["call", "put"], default="call")
    ap.add_argument("--implied-from", type=float, default=None,
                    help="observed price to invert into an implied volatility")
    ap.add_argument("--no-mc", action="store_true", help="skip Monte-Carlo comparison")
    ap.add_argument("--paths", type=int, default=500_000, help="Monte-Carlo path count")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args(argv)

    # Implied vol mode.
    if args.implied_from is not None:
        iv = implied_volatility(
            args.implied_from, args.S, args.K, args.T, args.r, args.q, args.kind
        )
        print(f"\nImplied volatility ({args.kind}) = {iv:.4%}\n")
        args.sigma = iv  # continue and show Greeks at the implied vol

    if args.sigma is None:
        ap.error("--sigma is required unless --implied-from is given")

    S, K, T, r, sigma, q, kind = (
        args.S, args.K, args.T, args.r, args.sigma, args.q, args.kind
    )

    g = bs_greeks(S, K, T, r, sigma, q, kind)
    print("=" * 58)
    print(f"  European {kind.upper()}   S={S}  K={K}  T={T}y  r={r:.2%}  "
          f"σ={sigma:.2%}  q={q:.2%}")
    print("=" * 58)
    print(f"  Price                 {_fmt(g.price)}")
    print(f"  Delta  (per $1 S)     {_fmt(g.delta)}")
    print(f"  Gamma  (per $1 S)     {_fmt(g.gamma)}")
    print(f"  Vega   (per 1% vol)   {_fmt(g.per_point_vega())}")
    print(f"  Theta  (per day)      {_fmt(g.per_day_theta())}")
    print(f"  Rho    (per 1% rate)  {_fmt(g.rho / 100.0)}")

    # Put-call parity sanity check.
    other = "put" if kind == "call" else "call"
    other_price = float(bs_price(S, K, T, r, sigma, q, other))
    call_p = g.price if kind == "call" else other_price
    put_p = g.price if kind == "put" else other_price
    gap = put_call_parity_gap(call_p, put_p, S, K, T, r, q)
    print(f"\n  Put-call parity residual: {gap:.2e}  (≈0 confirms consistency)")

    if not args.no_mc:
        print("\n" + "-" * 58)
        print("  Monte-Carlo cross-check")
        print("-" * 58)
        dfp = compare_prices(S, K, T, r, sigma, q, args.paths, args.seed)
        with_opts = dfp.to_string(index=False, float_format=lambda v: f"{v:.4f}")
        print(with_opts)
        print("\n  Greeks: analytic vs Monte-Carlo (finite difference)")
        dfg = compare_greeks(S, K, T, r, sigma, q, kind, args.paths, args.seed)
        print(dfg.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
