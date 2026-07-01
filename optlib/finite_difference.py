"""
Crank-Nicolson finite-difference solver for the Black-Scholes PDE

    ∂V/∂t + ½σ²S²·∂²V/∂S² + (r-q)S·∂V/∂S - rV = 0.

This is a fourth, grid-based pricing method (alongside closed-form BS, Monte
-Carlo, and the binomial tree). Crank-Nicolson is second-order accurate in both
time and space and unconditionally stable.

It prices:
  * European options (pure tridiagonal solve), and
  * American options (early exercise enforced each step via projection, i.e.
    V = max(V, payoff) after the implicit solve).

The grid also yields delta and gamma essentially for free (they are just finite
differences of the solved value surface at S₀).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.linalg import solve_banded


@dataclass(frozen=True)
class FDResult:
    price: float
    delta: float
    gamma: float
    S_grid: np.ndarray
    V_grid: np.ndarray  # value at t=0 across the spot grid


def crank_nicolson(
    S, K, T, r, sigma, q=0.0, kind="call", exercise="european",
    S_max_mult: float = 4.0, n_space: int = 400, n_time: int = 400,
) -> FDResult:
    """
    Price a European/American option on a uniform spot grid via Crank-Nicolson.

    Parameters
    ----------
    S_max_mult : the grid spans [0, S_max_mult * max(S, K)].
    n_space, n_time : grid resolution (more = more accurate, slower).
    """
    kind = kind.lower()
    american = exercise.lower() == "american"

    S_max = S_max_mult * max(S, K)
    N = n_space
    M = n_time
    dS = S_max / N
    dt = T / M
    i = np.arange(N + 1)
    S_grid = i * dS

    # Terminal payoff.
    if kind == "call":
        V = np.maximum(S_grid - K, 0.0)
    else:
        V = np.maximum(K - S_grid, 0.0)
    payoff = V.copy()

    # Interior CN coefficients (i = 1 .. N-1).
    ii = i[1:-1]
    alpha = 0.25 * dt * (sigma ** 2 * ii ** 2 - (r - q) * ii)
    beta = -0.5 * dt * (sigma ** 2 * ii ** 2 + r)
    gamma = 0.25 * dt * (sigma ** 2 * ii ** 2 + (r - q) * ii)

    # LHS tridiagonal M1 (unknown layer) in banded form for solve_banded.
    n_int = N - 1
    ab = np.zeros((3, n_int))
    ab[0, 1:] = -gamma[:-1]           # super-diagonal
    ab[1, :] = 1.0 - beta             # main diagonal
    ab[2, :-1] = -alpha[1:]           # sub-diagonal

    def boundary(tau, at):
        """Dirichlet boundary values at S=0 (at='low') / S=S_max (at='high')."""
        if kind == "call":
            return 0.0 if at == "low" else S_max * np.exp(-q * tau) - K * np.exp(-r * tau)
        else:
            return K * np.exp(-r * tau) if at == "low" else 0.0

    # March backward in time.
    for m in range(M, 0, -1):
        tau_new = (M - (m - 1)) * dt   # time-to-expiry at the layer we solve for
        tau_old = (M - m) * dt

        Vin = V[1:-1]
        rhs = alpha * V[:-2] + (1.0 + beta) * Vin + gamma * V[2:]

        low_new, high_new = boundary(tau_new, "low"), boundary(tau_new, "high")
        low_old, high_old = boundary(tau_old, "low"), boundary(tau_old, "high")
        # Add known boundary contributions (implicit + explicit halves).
        rhs[0] += alpha[0] * (low_old + low_new)
        rhs[-1] += gamma[-1] * (high_old + high_new)

        Vin_new = solve_banded((1, 1), ab, rhs)

        V = np.empty(N + 1)
        V[0], V[-1] = low_new, high_new
        V[1:-1] = Vin_new
        if american:
            V = np.maximum(V, payoff)

    # Read price + Greeks at S₀. Interpolate *centered on S* (S rarely lands on
    # a node) so the finite differences are second-order accurate rather than
    # picking up an O(dS) off-centering error.
    h = dS
    price = float(np.interp(S, S_grid, V))
    v_up = float(np.interp(S + h, S_grid, V))
    v_dn = float(np.interp(S - h, S_grid, V))
    delta = (v_up - v_dn) / (2 * h)
    gamma_val = (v_up - 2 * price + v_dn) / h ** 2
    return FDResult(price=price, delta=delta, gamma=gamma_val, S_grid=S_grid, V_grid=V)


def fd_price(S, K, T, r, sigma, q=0.0, kind="call", exercise="european", **kw) -> float:
    """Convenience wrapper returning just the price."""
    return crank_nicolson(S, K, T, r, sigma, q, kind, exercise, **kw).price
