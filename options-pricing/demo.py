#!/usr/bin/env python3
"""
End-to-end demonstration + report generator.

Running this script:
  1. prices a sample option analytically and prints all five Greeks,
  2. cross-checks against Monte-Carlo (price + Greeks + convergence table),
  3. generates every figure into ``figures/`` as PNGs.

    python demo.py
"""

from __future__ import annotations

import os

import pandas as pd

from optlib.black_scholes import bs_greeks
from optlib.compare import (
    compare_all_models,
    compare_greeks,
    compare_prices,
    convergence_table,
)
from optlib.strategy import bull_call_spread, iron_condor, straddle
from optlib import visualize as viz

pd.set_option("display.width", 120)
pd.set_option("display.float_format", lambda v: f"{v:.4f}")

# ------------------------------------------------------------------ sample contract
S, K, T, r, sigma, q = 100.0, 105.0, 0.75, 0.045, 0.28, 0.01
FIG_DIR = os.path.join(os.path.dirname(__file__), "figures")


def section(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def main():
    os.makedirs(FIG_DIR, exist_ok=True)

    section(f"Contract:  S={S}  K={K}  T={T}y  r={r:.2%}  σ={sigma:.2%}  q={q:.2%}")

    section("1. Black-Scholes price & Greeks")
    for kind in ("call", "put"):
        g = bs_greeks(S, K, T, r, sigma, q, kind)
        print(f"\n  {kind.upper()}")
        print(f"    price            {g.price:12.4f}")
        print(f"    delta            {g.delta:12.4f}")
        print(f"    gamma            {g.gamma:12.4f}")
        print(f"    vega  (/1% vol)  {g.per_point_vega():12.4f}")
        print(f"    theta (/day)     {g.per_day_theta():12.4f}")
        print(f"    rho   (/1% rate) {g.rho / 100.0:12.4f}")

    section("2. Black-Scholes vs Monte-Carlo — PRICE")
    print(compare_prices(S, K, T, r, sigma, q, n_paths=1_000_000).to_string(index=False))

    section("3. Black-Scholes vs Monte-Carlo — GREEKS (call)")
    print(compare_greeks(S, K, T, r, sigma, q, "call", n_paths=1_000_000).to_string(index=False))

    section("4. Three-model price comparison (call): BS vs MC vs Binomial")
    print(compare_all_models(S, K, T, r, sigma, q, "call").to_string(index=False))
    print("\n  (put — note the American early-exercise premium)")
    print(compare_all_models(S, K, T, r, sigma, q, "put").to_string(index=False))

    section("5. Monte-Carlo convergence (call)")
    print(convergence_table(S, K, T, r, sigma, q, "call").to_string(index=False))

    section("6. Multi-leg strategy analysis")
    for strat in (bull_call_spread(95, 110), straddle(K), iron_condor(85, 95, 110, 120)):
        p = strat.profile(S, T, r, sigma, q)
        gk = p["greeks"]
        be = ", ".join(f"{b:.2f}" for b in p["breakevens"]) or "none"
        print(f"\n  {p['name']}")
        print(f"    net premium   {p['net_premium']:+.4f}   "
              f"max profit {p['max_profit']:.4f}   max loss {p['max_loss']:.4f}")
        print(f"    breakevens    {be}")
        print(f"    Δ={gk['delta']:.4f}  Γ={gk['gamma']:.4f}  "
              f"V(/1%)={gk['vega']/100:.4f}  Θ(/day)={gk['theta']/365:.4f}  "
              f"ρ(/1%)={gk['rho']/100:.4f}")

    section("7. Generating figures -> figures/")
    figures = {
        "greeks_vs_spot.png": lambda p: viz.plot_greeks_vs_spot(K, T, r, sigma, q, "call", save_path=p),
        "vol_smile.png": lambda p: viz.plot_vol_smile(S=S, save_path=p),
        "vol_surface.png": lambda p: viz.plot_vol_surface(S=S, save_path=p),
        "mc_convergence.png": lambda p: viz.plot_mc_convergence(S, K, T, r, sigma, q, "call", save_path=p),
        "model_convergence.png": lambda p: viz.plot_model_convergence(S, K, T, r, sigma, q, "call", save_path=p),
        "payoff_diagram.png": lambda p: viz.plot_payoff_diagram(S, K, T, r, sigma, q, "call", save_path=p),
        "sample_paths.png": lambda p: viz.plot_sample_paths(S, K, T, r, sigma, q, "call", save_path=p),
        "strategy_iron_condor.png": lambda p: viz.plot_strategy_pnl(iron_condor(85, 95, 110, 120), S, T, r, sigma, q, save_path=p),
    }
    for name, fn in figures.items():
        path = os.path.join(FIG_DIR, name)
        fn(path)
        print(f"    wrote {path}")

    print("\nDone. See figures/ for the visualizations.\n")


if __name__ == "__main__":
    main()
