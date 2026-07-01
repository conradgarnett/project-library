"""
Alternative underlying-dynamics models beyond plain geometric Brownian motion.

These relax the two most unrealistic Black-Scholes assumptions — constant
volatility and continuous paths — and both *endogenously* produce the implied
volatility smile/skew that BS cannot:

  Merton jump-diffusion : GBM plus lognormal jumps at Poisson times. Closed form
      (a Poisson-weighted sum of Black-Scholes prices) + a Monte-Carlo pricer.
  Heston stochastic vol : variance follows a mean-reverting CIR process
      correlated with the spot. Monte-Carlo pricer (full-truncation Euler).

Both reduce to Black-Scholes in the appropriate limit (no jumps / zero vol-of
-vol), which is used as a correctness check in the tests.
"""

from __future__ import annotations

import math

import numpy as np

from .black_scholes import bs_price


# ======================================================================= #
# Merton jump-diffusion
# ======================================================================= #
def merton_jump_price(
    S, K, T, r, sigma, q=0.0, kind="call",
    lam=1.0, muJ=-0.1, sigJ=0.15, n_terms=60,
) -> float:
    """
    Closed-form Merton (1976) jump-diffusion price.

    Jumps arrive as a Poisson process with intensity ``lam``; each jump
    multiplies the price by exp(J) with J ~ N(muJ, sigJ²). The price is a
    Poisson-weighted sum of Black-Scholes prices with adjusted vol and rate.
    """
    kind = kind.lower()
    k = math.exp(muJ + 0.5 * sigJ ** 2) - 1.0     # mean proportional jump size
    lam_p = lam * (1.0 + k)
    total = 0.0
    for n in range(n_terms):
        sigma_n = math.sqrt(sigma ** 2 + n * sigJ ** 2 / T)
        r_n = r - lam * k + n * math.log(1.0 + k) / T
        weight = math.exp(-lam_p * T) * (lam_p * T) ** n / math.factorial(n)
        total += weight * bs_price(S, K, T, r_n, sigma_n, q, kind)
    return float(total)


def merton_jump_price_mc(
    S, K, T, r, sigma, q=0.0, kind="call",
    lam=1.0, muJ=-0.1, sigJ=0.15, n_paths=400_000, seed=42,
):
    """Monte-Carlo Merton pricer (terminal-price simulation). Returns (price, se)."""
    kind = kind.lower()
    rng = np.random.default_rng(seed)
    k = math.exp(muJ + 0.5 * sigJ ** 2) - 1.0

    Zc = rng.standard_normal(n_paths)                       # diffusion shock
    Njumps = rng.poisson(lam * T, n_paths)                  # jump counts
    # Sum of Njumps normal jumps: N(Njumps*muJ, Njumps*sigJ²).
    jump = rng.standard_normal(n_paths) * (np.sqrt(Njumps) * sigJ) + Njumps * muJ

    drift = (r - q - lam * k - 0.5 * sigma ** 2) * T
    S_T = S * np.exp(drift + sigma * np.sqrt(T) * Zc + jump)
    payoff = np.maximum(S_T - K, 0.0) if kind == "call" else np.maximum(K - S_T, 0.0)
    disc = np.exp(-r * T) * payoff
    return float(disc.mean()), float(disc.std(ddof=1) / np.sqrt(n_paths))


# ======================================================================= #
# Heston stochastic volatility
# ======================================================================= #
def heston_price_mc(
    S, K, T, r, q=0.0, kind="call",
    v0=0.04, kappa=2.0, theta=0.04, xi=0.3, rho=-0.7,
    n_paths=200_000, n_steps=200, seed=42,
):
    """
    Heston model price via full-truncation Euler Monte-Carlo.

        dS = (r-q)S dt + sqrt(v) S dW1
        dv = kappa(theta - v) dt + xi sqrt(v) dW2,   corr(dW1, dW2) = rho

    Parameters: v0 initial variance, kappa mean-reversion speed, theta long-run
    variance, xi vol-of-vol, rho spot/vol correlation (negative => equity skew).
    Returns (price, std_error). Reduces to Black-Scholes as xi -> 0 with
    v0 = theta = sigma².
    """
    kind = kind.lower()
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    sqrt_dt = math.sqrt(dt)

    logS = np.full(n_paths, math.log(S))
    v = np.full(n_paths, v0)
    for _ in range(n_steps):
        z1 = rng.standard_normal(n_paths)
        z2 = rho * z1 + math.sqrt(1.0 - rho ** 2) * rng.standard_normal(n_paths)
        v_pos = np.maximum(v, 0.0)                          # full truncation
        logS += (r - q - 0.5 * v_pos) * dt + np.sqrt(v_pos) * sqrt_dt * z1
        v += kappa * (theta - v_pos) * dt + xi * np.sqrt(v_pos) * sqrt_dt * z2

    S_T = np.exp(logS)
    payoff = np.maximum(S_T - K, 0.0) if kind == "call" else np.maximum(K - S_T, 0.0)
    disc = np.exp(-r * T) * payoff
    return float(disc.mean()), float(disc.std(ddof=1) / np.sqrt(n_paths))
