"""
Cox-Ross-Rubinstein (CRR) binomial tree pricer.

Adds a third, lattice-based pricing method alongside Black-Scholes (closed form)
and Monte-Carlo (simulation). Unlike the other two it also prices **American**
options (early exercise), which have no simple closed form.

As the number of steps grows the European tree price converges to the
Black-Scholes price, giving a second independent validation of the analytic
model.

Reference: Cox, Ross & Rubinstein (1979).
"""

from __future__ import annotations

from typing import Literal

import numpy as np

OptionKind = Literal["call", "put"]
Exercise = Literal["european", "american"]


def binomial_price(
    S, K, T, r, sigma, q=0.0, kind: OptionKind = "call",
    exercise: Exercise = "european", n_steps: int = 500,
) -> float:
    """
    Price a European or American option on a CRR binomial tree.

    Parameters
    ----------
    n_steps : number of time steps in the lattice (more = more accurate).
    exercise : "european" (exercise only at expiry) or "american"
        (exercise allowed at any node).
    """
    kind = kind.lower()  # tolerate case
    if T <= 0:
        payoff = (S - K) if kind == "call" else (K - S)
        return max(payoff, 0.0)

    dt = T / n_steps
    u = np.exp(sigma * np.sqrt(dt))
    d = 1.0 / u
    disc = np.exp(-r * dt)
    # Risk-neutral up-probability with dividend yield.
    p = (np.exp((r - q) * dt) - d) / (u - d)
    if not (0.0 <= p <= 1.0):
        raise ValueError(
            f"risk-neutral probability {p:.4f} outside [0,1]; "
            "increase n_steps or check inputs"
        )

    # Terminal underlying prices: S * u^j * d^(n-j), j = 0..n.
    j = np.arange(n_steps + 1)
    ST = S * u ** j * d ** (n_steps - j)
    if kind == "call":
        values = np.maximum(ST - K, 0.0)
    else:
        values = np.maximum(K - ST, 0.0)

    # Backward induction.
    american = exercise.lower() == "american"
    for step in range(n_steps - 1, -1, -1):
        values = disc * (p * values[1:] + (1.0 - p) * values[:-1])
        if american:
            j = np.arange(step + 1)
            S_node = S * u ** j * d ** (step - j)
            intrinsic = (S_node - K) if kind == "call" else (K - S_node)
            values = np.maximum(values, np.maximum(intrinsic, 0.0))

    return float(values[0])


def binomial_greeks(
    S, K, T, r, sigma, q=0.0, kind: OptionKind = "call",
    exercise: Exercise = "european", n_steps: int = 500,
) -> dict:
    """
    Finite-difference Greeks from the binomial tree (bump-and-revalue).
    Returns the same keys as :func:`optlib.bs_greeks`, matching units.
    """
    def price(S_, K_, T_, r_, sig_, q_):
        return binomial_price(S_, K_, T_, r_, sig_, q_, kind, exercise, n_steps)

    dS = S * 1e-3
    dSig, dr, dT = 1e-3, 1e-4, 1.0 / 365.0
    base = price(S, K, T, r, sigma, q)
    up_s, dn_s = price(S + dS, K, T, r, sigma, q), price(S - dS, K, T, r, sigma, q)
    return {
        "price": base,
        "delta": (up_s - dn_s) / (2 * dS),
        "gamma": (up_s - 2 * base + dn_s) / dS ** 2,
        "vega": (price(S, K, T, r, sigma + dSig, q) - price(S, K, T, r, sigma - dSig, q)) / (2 * dSig),
        "rho": (price(S, K, T, r + dr, sigma, q) - price(S, K, T, r - dr, sigma, q)) / (2 * dr),
        "theta": (price(S, K, max(T - dT, 1e-8), r, sigma, q) - base) / dT,
    }
