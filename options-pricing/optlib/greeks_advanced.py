"""
Higher-order (second- and third-order) Greeks for Black-Scholes-Merton.

The first-order set (delta, gamma, vega, theta, rho) lives in
``optlib.black_scholes``. This module adds the cross- and higher-order
sensitivities that desks use to manage the risk *of the risk*:

  vanna       ∂²V/∂S∂σ   — how delta moves with vol (and vega with spot)
  charm       ∂Δ/∂T      — delta decay through time ("delta bleed")
  vomma/volga ∂²V/∂σ²    — convexity of vega in vol
  veta        ∂vega/∂T   — vega decay through time
  speed       ∂³V/∂S³    — rate of change of gamma with spot
  zomma       ∂γ/∂σ      — rate of change of gamma with vol
  color       ∂γ/∂T      — gamma decay through time
  ultima      ∂³V/∂σ³    — third-order vol sensitivity (rate of change of vomma)
  dual_delta  ∂V/∂K      — sensitivity to strike (≈ -disc·risk-neutral P(ITM))
  dual_gamma  ∂²V/∂K²

Every formula is expressed with a continuous dividend yield ``q`` and is unit-
tested against an independent finite difference of the relevant first-order
Greek (see ``tests/test_advanced_greeks.py``).

Sign convention: all quantities are the plain partial derivatives named above.
In particular ``charm``/``veta``/``color`` are derivatives with respect to time
to expiry ``T``; as *calendar* time passes T shrinks, so the per-day "bleed" of
a Greek is ``-<greek>/365``.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
from scipy.stats import norm

from .black_scholes import _d1_d2, _norm_pdf  # reuse validated internals


@dataclass(frozen=True)
class AdvancedGreeks:
    vanna: float
    charm: float
    vomma: float
    veta: float
    speed: float
    zomma: float
    color: float
    ultima: float
    dual_delta: float
    dual_gamma: float

    def as_dict(self) -> dict:
        return asdict(self)


def advanced_greeks(S, K, T, r, sigma, q=0.0, kind="call") -> AdvancedGreeks:
    """Return all higher-order Greeks for a European option (scalar inputs)."""
    kind = kind.lower()
    S, K, T, r, sigma, q = (float(x) for x in (S, K, T, r, sigma, q))
    if T <= 0 or sigma <= 0:
        z = 0.0
        return AdvancedGreeks(z, z, z, z, z, z, z, z, z, z)

    srt = np.sqrt(T)
    Dq = np.exp(-q * T)
    Dr = np.exp(-r * T)
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    phi = _norm_pdf(d1)          # standard-normal pdf at d1
    b = r - q                    # cost of carry

    gamma = Dq * phi / (S * sigma * srt)
    vega = S * Dq * phi * srt

    # --- second order -----------------------------------------------------
    vanna = -Dq * phi * d2 / sigma
    vomma = vega * d1 * d2 / sigma

    if kind == "call":
        charm = q * Dq * norm.cdf(d1) - Dq * phi * (2 * b * T - d2 * sigma * srt) / (
            2 * T * sigma * srt
        )
    else:
        charm = -q * Dq * norm.cdf(-d1) - Dq * phi * (2 * b * T - d2 * sigma * srt) / (
            2 * T * sigma * srt
        )
    # Haug's DdeltaDtime is -∂Δ/∂T; flip so `charm` == ∂Δ/∂T.
    charm = -charm

    veta = (
        S * Dq * phi * srt
        * (q + b * d1 / (sigma * srt) - (1.0 + d1 * d2) / (2.0 * T))
    )
    # Haug's DvegaDtime is ∂vega/∂(calendar t) = -∂vega/∂T; flip to ∂vega/∂T.
    veta = -veta

    # --- third order ------------------------------------------------------
    speed = -gamma / S * (d1 / (sigma * srt) + 1.0)
    zomma = gamma * (d1 * d2 - 1.0) / sigma
    # This standard form already equals ∂γ/∂T (verified against finite diff).
    color = (
        -Dq * phi / (2.0 * S * T * sigma * srt)
        * (2 * q * T + 1.0 + (2 * b * T - d2 * sigma * srt) / (sigma * srt) * d1)
    )
    ultima = -vega / sigma ** 2 * (d1 * d2 * (1.0 - d1 * d2) + d1 ** 2 + d2 ** 2)

    # --- strike sensitivities --------------------------------------------
    if kind == "call":
        dual_delta = -Dr * norm.cdf(d2)
    else:
        dual_delta = Dr * norm.cdf(-d2)
    dual_gamma = Dr * phi / (K * sigma * srt)

    return AdvancedGreeks(
        vanna=float(vanna),
        charm=float(charm),
        vomma=float(vomma),
        veta=float(veta),
        speed=float(speed),
        zomma=float(zomma),
        color=float(color),
        ultima=float(ultima),
        dual_delta=float(dual_delta),
        dual_gamma=float(dual_gamma),
    )
