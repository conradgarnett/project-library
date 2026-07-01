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
from optlib.greeks_advanced import advanced_greeks
from optlib.exotic import (
    asian_price_mc,
    barrier_price,
    digital_price,
    geometric_asian_price,
    lookback_price_mc,
)
from optlib.models import heston_price_mc, merton_jump_price
from optlib.black_scholes import implied_volatility
from optlib.implied import (
    delta_hedge_pnl,
    implied_prob_itm,
    realized_volatility,
    variance_risk_premium,
)
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

    section("7. Higher-order (advanced) Greeks — call")
    ag = advanced_greeks(S, K, T, r, sigma, q, "call")
    for name, val in ag.as_dict().items():
        print(f"    {name:12s} {val:12.5f}")

    section("8. Exotic options")
    print(f"    digital call (cash-or-nothing $1)   {digital_price(S, K, T, r, sigma, q, 'call'):.4f}")
    print(f"    geometric Asian call (closed form)  {geometric_asian_price(S, K, T, r, sigma, q, 'call'):.4f}")
    a_mc, a_se = asian_price_mc(S, K, T, r, sigma, q, 'call', 'arithmetic', n_paths=200_000)
    print(f"    arithmetic Asian call (MC+control)  {a_mc:.4f} ± {a_se:.4f}")
    dao = barrier_price(S, K, 90, T, r, sigma, q, 'call', 'down-out')
    print(f"    down-and-out call (H=90, barrier)   {dao:.4f}")
    lb, lse = lookback_price_mc(S, T, r, sigma, q, 'call', n_paths=200_000)
    print(f"    floating-strike lookback call (MC)  {lb:.4f} ± {lse:.4f}")

    section("9. Alternative models & the volatility smile they generate")
    for Kx in (85, 100, 115):
        pm = merton_jump_price(S, Kx, T, r, 0.20, q, 'call', lam=1.0, muJ=-0.12, sigJ=0.15)
        ivm = implied_volatility(pm, S, Kx, T, r, q, 'call')
        ph, _ = heston_price_mc(S, Kx, T, r, q, 'call', v0=0.04, kappa=2.0, theta=0.04,
                                xi=0.5, rho=-0.7, n_paths=150_000, n_steps=150)
        ivh = implied_volatility(ph, S, Kx, T, r, q, 'call')
        print(f"    K={Kx}: Merton IV={ivm:.4f}   Heston IV={ivh:.4f}   (flat BS = 0.2000)")

    section("10. Implied vs realized — fact-checking the model")
    iv = 0.20
    print(f"    implied ITM prob N(d2) (risk-neutral): "
          f"{implied_prob_itm(S, K, T, r, iv, q, 'call'):.4f}")
    print(f"    real-world ITM prob (mu=10%):          "
          f"{implied_prob_itm(S, K, T, r, iv, q, 'call', 'real-world', mu=0.10):.4f}"
          f"   (gap = risk premium)")
    vrp = variance_risk_premium(implied_vol=0.20, realized_vol=0.16)
    print(f"    variance risk premium: IV=20% RV=16% -> "
          f"{vrp.vrp_vol_points*100:+.1f} vol pts (options were rich)")
    print("    delta-hedged LONG call P&L vs realized vol (implied=20%):")
    for rv in (0.10, 0.20, 0.30):
        res = delta_hedge_pnl(S, K, T, r, 0.20, rv, q, 'call', 'long',
                              n_steps=126, n_paths=40_000)
        print(f"       realized={rv:.0%}: P&L={res['mean_pnl']:+.4f} "
              f"(predicted {res['predicted_pnl']:+.4f})")

    section("11. Generating figures -> figures/")
    figures = {
        "greeks_vs_spot.png": lambda p: viz.plot_greeks_vs_spot(K, T, r, sigma, q, "call", save_path=p),
        "vol_smile.png": lambda p: viz.plot_vol_smile(S=S, save_path=p),
        "vol_surface.png": lambda p: viz.plot_vol_surface(S=S, save_path=p),
        "mc_convergence.png": lambda p: viz.plot_mc_convergence(S, K, T, r, sigma, q, "call", save_path=p),
        "model_convergence.png": lambda p: viz.plot_model_convergence(S, K, T, r, sigma, q, "call", save_path=p),
        "payoff_diagram.png": lambda p: viz.plot_payoff_diagram(S, K, T, r, sigma, q, "call", save_path=p),
        "sample_paths.png": lambda p: viz.plot_sample_paths(S, K, T, r, sigma, q, "call", save_path=p),
        "strategy_iron_condor.png": lambda p: viz.plot_strategy_pnl(iron_condor(85, 95, 110, 120), S, T, r, sigma, q, save_path=p),
        "risk_neutral_density.png": lambda p: viz.plot_risk_neutral_density(S, K, T, r, sigma, q, save_path=p),
        "iv_vs_realized_hedge.png": lambda p: viz.plot_iv_vs_realized_hedge(S, K, T, r, 0.28, q, "call", save_path=p),
        "model_smiles.png": lambda p: viz.plot_model_smiles(S=S, T=1.0, r=r, save_path=p),
    }
    for name, fn in figures.items():
        path = os.path.join(FIG_DIR, name)
        fn(path)
        print(f"    wrote {path}")

    print("\nDone. See figures/ for the visualizations.\n")


if __name__ == "__main__":
    main()
