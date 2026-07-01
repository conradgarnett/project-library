"""
Head-to-head comparison of the closed-form Black-Scholes pricer against the
Monte-Carlo pricer, for both prices and Greeks.

The point of the comparison is twofold:
  1. Validation — the analytic price is the ground truth; a correct MC estimate
     should sit inside its own 95% confidence interval around that truth.
  2. Intuition — it shows how MC error shrinks like 1/sqrt(N).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .binomial import binomial_price
from .black_scholes import bs_greeks, bs_price
from .monte_carlo import MonteCarloPricer


def compare_prices(
    S, K, T, r, sigma, q=0.0,
    n_paths=500_000, seed=42,
) -> pd.DataFrame:
    """
    Compare BS vs MC prices for both a call and a put on the same contract.

    Returns a tidy DataFrame with the analytic price, the MC price, MC standard
    error, 95% CI, the absolute error, and whether the analytic price falls
    inside the MC confidence interval (the key correctness check).
    """
    mc = MonteCarloPricer(n_paths=n_paths, seed=seed)
    rows = []
    for kind in ("call", "put"):
        bs = float(bs_price(S, K, T, r, sigma, q, kind))
        res = mc.price(S, K, T, r, sigma, q, kind)
        err = res.price - bs
        rows.append(
            {
                "kind": kind,
                "black_scholes": bs,
                "monte_carlo": res.price,
                "mc_std_error": res.std_error,
                "ci_low": res.ci_low,
                "ci_high": res.ci_high,
                "abs_error": abs(err),
                "err_in_std_errors": err / res.std_error if res.std_error else np.nan,
                "bs_within_ci": res.ci_low <= bs <= res.ci_high,
            }
        )
    return pd.DataFrame(rows)


def compare_all_models(
    S, K, T, r, sigma, q=0.0, kind="call",
    n_paths=1_000_000, n_steps=1000, seed=42,
) -> pd.DataFrame:
    """
    Three-way price comparison: Black-Scholes (closed form), Monte-Carlo
    (simulation), and CRR binomial tree (lattice), plus the American binomial
    price to show the early-exercise premium.

    All three European numbers should agree to within Monte-Carlo error.
    """
    bs = float(bs_price(S, K, T, r, sigma, q, kind))
    mc = MonteCarloPricer(n_paths=n_paths, seed=seed).price(S, K, T, r, sigma, q, kind)
    euro = binomial_price(S, K, T, r, sigma, q, kind, "european", n_steps)
    amer = binomial_price(S, K, T, r, sigma, q, kind, "american", n_steps)
    return pd.DataFrame(
        [
            {"model": "Black-Scholes (closed form)", "price": bs, "note": "analytic truth"},
            {"model": "Monte-Carlo (simulation)", "price": mc.price,
             "note": f"±{mc.std_error:.4f} SE (95% CI {mc.ci_low:.4f}-{mc.ci_high:.4f})"},
            {"model": "Binomial tree, European", "price": euro,
             "note": f"{n_steps} steps; err vs BS = {abs(euro - bs):.4f}"},
            {"model": "Binomial tree, American", "price": amer,
             "note": f"early-exercise premium = {amer - euro:.4f}"},
        ]
    )


def compare_greeks(
    S, K, T, r, sigma, q=0.0, kind="call",
    n_paths=500_000, seed=42,
) -> pd.DataFrame:
    """
    Compare all five Greeks (plus price): analytic vs MC finite-difference.
    """
    analytic = bs_greeks(S, K, T, r, sigma, q, kind).as_dict()
    mc = MonteCarloPricer(n_paths=n_paths, seed=seed).greeks(
        S, K, T, r, sigma, q, kind
    )
    rows = []
    for g in ("price", "delta", "gamma", "vega", "theta", "rho"):
        a, m = analytic[g], mc[g]
        rows.append(
            {
                "greek": g,
                "black_scholes": a,
                "monte_carlo": m,
                "abs_error": abs(m - a),
                "rel_error_%": (abs(m - a) / abs(a) * 100.0) if a else np.nan,
            }
        )
    return pd.DataFrame(rows)


def convergence_table(
    S, K, T, r, sigma, q=0.0, kind="call",
    path_counts=(1_000, 5_000, 25_000, 100_000, 500_000, 2_000_000),
    seed=42,
) -> pd.DataFrame:
    """
    Show MC price + standard error as the number of paths grows, next to the
    analytic price, to illustrate O(1/sqrt(N)) convergence.
    """
    truth = float(bs_price(S, K, T, r, sigma, q, kind))
    rows = []
    for n in path_counts:
        res = MonteCarloPricer(n_paths=n, seed=seed).price(S, K, T, r, sigma, q, kind)
        rows.append(
            {
                "n_paths": n,
                "mc_price": res.price,
                "std_error": res.std_error,
                "abs_error": abs(res.price - truth),
                "bs_price": truth,
                "bs_within_ci": res.ci_low <= truth <= res.ci_high,
            }
        )
    return pd.DataFrame(rows)
