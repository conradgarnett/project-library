"""
Risk-neutral Monte-Carlo pricing of European options under geometric Brownian
motion, with:

  * antithetic variates + optional control variate (variance reduction),
  * a proper standard error and 95% confidence interval on the price,
  * finite-difference Greeks computed with **common random numbers** so the
    bump-and-revalue estimates are stable (low variance),
  * path generation for visualisation.

Under the risk-neutral measure the terminal underlying price is

    S_T = S0 * exp( (r - q - 0.5 sigma^2) T + sigma sqrt(T) Z ),  Z ~ N(0,1)

and the option value is  exp(-rT) * E[ payoff(S_T) ].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from .black_scholes import bs_price

OptionKind = Literal["call", "put"]


@dataclass(frozen=True)
class MCResult:
    """Outcome of a Monte-Carlo pricing run."""

    price: float
    std_error: float
    ci_low: float
    ci_high: float
    n_paths: int
    kind: OptionKind

    def __repr__(self) -> str:
        return (
            f"MCResult(price={self.price:.4f}, se={self.std_error:.4f}, "
            f"95% CI=[{self.ci_low:.4f}, {self.ci_high:.4f}], "
            f"n={self.n_paths:,}, kind={self.kind!r})"
        )


def _payoff(S_T: np.ndarray, K: float, kind: OptionKind) -> np.ndarray:
    if kind == "call":
        return np.maximum(S_T - K, 0.0)
    return np.maximum(K - S_T, 0.0)


def _terminal_prices(S, r, q, sigma, T, Z):
    drift = (r - q - 0.5 * sigma ** 2) * T
    diffusion = sigma * np.sqrt(T) * Z
    return S * np.exp(drift + diffusion)


class MonteCarloPricer:
    """
    Configurable Monte-Carlo pricer. One instance can price calls/puts and
    estimate Greeks while reusing the same random-number stream.

    Parameters
    ----------
    n_paths : number of simulated terminal prices (before antithetic doubling).
    antithetic : if True, also simulate -Z, halving variance for ~free.
    control_variate : if True, use the discounted underlying as a control
        variate (its expectation is known exactly), further cutting variance.
    seed : RNG seed for reproducibility.
    """

    def __init__(
        self,
        n_paths: int = 200_000,
        antithetic: bool = True,
        control_variate: bool = True,
        seed: int | None = 42,
    ):
        self.n_paths = int(n_paths)
        self.antithetic = antithetic
        self.control_variate = control_variate
        self.seed = seed

    # ------------------------------------------------------------------ #
    def _draw_normals(self, rng: np.random.Generator) -> np.ndarray:
        if self.antithetic:
            half = rng.standard_normal(self.n_paths // 2 + self.n_paths % 2)
            Z = np.concatenate([half, -half])[: self.n_paths]
        else:
            Z = rng.standard_normal(self.n_paths)
        return Z

    def price(
        self, S, K, T, r, sigma, q=0.0, kind: OptionKind = "call",
        Z: np.ndarray | None = None,
    ) -> MCResult:
        """Price a European option and quantify Monte-Carlo error."""
        kind = kind.lower()  # tolerate 'Call'/'PUT'
        if Z is None:
            rng = np.random.default_rng(self.seed)
            Z = self._draw_normals(rng)
        n = Z.size

        disc = np.exp(-r * T)
        S_T = _terminal_prices(S, r, q, sigma, T, Z)
        payoff = _payoff(S_T, K, kind)
        discounted = disc * payoff

        if self.control_variate and T > 0:
            # Control variate: discounted terminal price has known mean S*e^{-qT}.
            cv = disc * S_T
            cv_mean_true = S * np.exp(-q * T)
            cov = np.cov(discounted, cv, ddof=1)
            beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0.0
            adjusted = discounted - beta * (cv - cv_mean_true)
        else:
            adjusted = discounted

        price = float(np.mean(adjusted))
        std_error = float(np.std(adjusted, ddof=1) / np.sqrt(n))
        z95 = 1.959963984540054
        return MCResult(
            price=price,
            std_error=std_error,
            ci_low=price - z95 * std_error,
            ci_high=price + z95 * std_error,
            n_paths=n,
            kind=kind,  # type: ignore[arg-type]
        )

    # ------------------------------------------------------------------ #
    def greeks(
        self, S, K, T, r, sigma, q=0.0, kind: OptionKind = "call",
        dS_rel=1e-2, dSigma=1e-2, dr=1e-4, dT=1.0 / 365.0,
    ) -> dict:
        """
        Finite-difference Greeks using **common random numbers** — every bumped
        revaluation reuses the exact same normal draws, so the differencing
        noise cancels and the Greek estimates are far more accurate than
        independently-simulated bumps.

        Returns a dict with the same five Greeks as :func:`optlib.bs_greeks`,
        in matching units.
        """
        kind = kind.lower()
        rng = np.random.default_rng(self.seed)
        Z = self._draw_normals(rng)

        def p(S_, K_, T_, r_, sig_, q_):
            return self.price(S_, K_, T_, r_, sig_, q_, kind, Z=Z).price

        dS = S * dS_rel
        base = p(S, K, T, r, sigma, q)

        # Central differences for delta/gamma/vega/rho.
        up_S, dn_S = p(S + dS, K, T, r, sigma, q), p(S - dS, K, T, r, sigma, q)
        delta = (up_S - dn_S) / (2 * dS)
        gamma = (up_S - 2 * base + dn_S) / (dS ** 2)

        up_v = p(S, K, T, r, sigma + dSigma, q)
        dn_v = p(S, K, T, r, sigma - dSigma, q)
        vega = (up_v - dn_v) / (2 * dSigma)  # per 1.00 sigma

        up_r = p(S, K, T, r + dr, sigma, q)
        dn_r = p(S, K, T, r - dr, sigma, q)
        rho = (up_r - dn_r) / (2 * dr)  # per 1.00 r

        # Theta: value decays as T shrinks. dV/dt = -dV/dT.
        T_dn = max(T - dT, 1e-8)
        theta = (p(S, K, T_dn, r, sigma, q) - base) / dT  # per year

        return {
            "price": base,
            "delta": delta,
            "gamma": gamma,
            "vega": vega,
            "theta": theta,
            "rho": rho,
        }

    # ------------------------------------------------------------------ #
    def simulate_paths(
        self, S, T, r, sigma, q=0.0, n_paths=50, n_steps=252,
        seed: int | None = None,
    ) -> np.ndarray:
        """
        Generate full GBM sample paths (for visualisation), shape
        ``(n_paths, n_steps + 1)`` including the initial price column.
        """
        rng = np.random.default_rng(self.seed if seed is None else seed)
        dt = T / n_steps
        drift = (r - q - 0.5 * sigma ** 2) * dt
        vol = sigma * np.sqrt(dt)
        shocks = rng.standard_normal((n_paths, n_steps))
        log_paths = np.cumsum(drift + vol * shocks, axis=1)
        paths = S * np.exp(log_paths)
        return np.hstack([np.full((n_paths, 1), float(S)), paths])


def mc_price(S, K, T, r, sigma, q=0.0, kind="call", n_paths=200_000, seed=42) -> MCResult:
    """Functional one-shot convenience wrapper around :class:`MonteCarloPricer`."""
    return MonteCarloPricer(n_paths=n_paths, seed=seed).price(
        S, K, T, r, sigma, q, kind
    )
