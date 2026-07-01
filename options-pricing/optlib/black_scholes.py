"""
Closed-form Black-Scholes-Merton pricing, the full set of first- and
second-order Greeks, and a robust implied-volatility solver.

All formulas support a continuous dividend yield ``q`` (Merton extension) and
reduce to the classic Black-Scholes model when ``q = 0``.

References
----------
Hull, *Options, Futures, and Other Derivatives*, chapters 15 & 19.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Literal

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

OptionKind = Literal["call", "put"]

_SQRT_2PI = np.sqrt(2.0 * np.pi)


def _norm_pdf(x: np.ndarray | float) -> np.ndarray | float:
    return np.exp(-0.5 * np.asarray(x, dtype=float) ** 2) / _SQRT_2PI


def _norm_cdf(x: np.ndarray | float) -> np.ndarray | float:
    return norm.cdf(x)


def _validate_kind(kind: str) -> OptionKind:
    k = kind.lower().strip()
    if k not in ("call", "put"):
        raise ValueError(f"kind must be 'call' or 'put', got {kind!r}")
    return k  # type: ignore[return-value]


# --------------------------------------------------------------------------- #
# Data containers
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class OptionParams:
    """Immutable bundle of the standard option parameters."""

    S: float
    K: float
    T: float
    r: float
    sigma: float
    q: float = 0.0
    kind: OptionKind = "call"

    def __post_init__(self) -> None:
        object.__setattr__(self, "kind", _validate_kind(self.kind))
        if self.S <= 0 or self.K <= 0:
            raise ValueError("S and K must be positive")
        if self.T < 0:
            raise ValueError("T (time to expiry) must be non-negative")
        if self.sigma < 0:
            raise ValueError("sigma must be non-negative")


@dataclass(frozen=True)
class Greeks:
    """The five standard Greeks (plus price for convenience)."""

    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float

    def as_dict(self) -> dict:
        return asdict(self)

    def per_day_theta(self) -> float:
        """Theta expressed per calendar day."""
        return self.theta / 365.0

    def per_point_vega(self) -> float:
        """Vega expressed per 1 volatility point (1%)."""
        return self.vega / 100.0


# --------------------------------------------------------------------------- #
# Core d1 / d2
# --------------------------------------------------------------------------- #
def _d1_d2(S, K, T, r, sigma, q):
    S = np.asarray(S, dtype=float)
    K = np.asarray(K, dtype=float)
    T = np.asarray(T, dtype=float)
    sigma = np.asarray(sigma, dtype=float)
    vol_sqrt_t = sigma * np.sqrt(T)
    # Guard against divide-by-zero at expiry or zero vol; handled by callers.
    with np.errstate(divide="ignore", invalid="ignore"):
        d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / vol_sqrt_t
        d2 = d1 - vol_sqrt_t
    return d1, d2


# --------------------------------------------------------------------------- #
# Pricing
# --------------------------------------------------------------------------- #
def bs_price(S, K, T, r, sigma, q=0.0, kind: OptionKind = "call"):
    """
    Black-Scholes-Merton price of a European option.

    Scalars or numpy arrays may be passed for any of S, K, T, sigma (they are
    broadcast together). Returns the option present value.

    Degenerate cases are handled analytically:
      * T == 0        -> intrinsic value max(S-K, 0) / max(K-S, 0)
      * sigma == 0    -> discounted deterministic payoff
    """
    kind = _validate_kind(kind)
    S = np.asarray(S, dtype=float)
    K = np.asarray(K, dtype=float)
    T = np.asarray(T, dtype=float)
    sigma = np.asarray(sigma, dtype=float)

    disc_r = np.exp(-r * T)
    disc_q = np.exp(-q * T)

    # Intrinsic (used for T->0 or sigma->0 forward-intrinsic).
    fwd = S * disc_q  # PV of receiving the (dividend-adjusted) underlying
    if kind == "call":
        intrinsic = np.maximum(fwd - K * disc_r, 0.0)
    else:
        intrinsic = np.maximum(K * disc_r - fwd, 0.0)

    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    if kind == "call":
        price = S * disc_q * _norm_cdf(d1) - K * disc_r * _norm_cdf(d2)
    else:
        price = K * disc_r * _norm_cdf(-d2) - S * disc_q * _norm_cdf(-d1)

    price = np.asarray(price, dtype=float)
    degenerate = (T <= 0) | (sigma <= 0)
    price = np.where(degenerate, intrinsic, price)
    return price.item() if price.ndim == 0 else price


# --------------------------------------------------------------------------- #
# Greeks
# --------------------------------------------------------------------------- #
def bs_greeks(S, K, T, r, sigma, q=0.0, kind: OptionKind = "call") -> Greeks:
    """
    Return price + all five Greeks (delta, gamma, vega, theta, rho).

    Scalar inputs only (returns a :class:`Greeks`). For vectorised Greek curves
    use :func:`optlib.visualize` helpers or call this in a comprehension.
    """
    kind = _validate_kind(kind)
    S, K, T, r, sigma, q = (float(x) for x in (S, K, T, r, sigma, q))

    price = float(bs_price(S, K, T, r, sigma, q, kind))

    # Degenerate expiry / zero-vol: Greeks are (mostly) undefined; return
    # sensible limiting values instead of NaNs.
    if T <= 0 or sigma <= 0:
        itm = (S > K) if kind == "call" else (S < K)
        delta = (1.0 if kind == "call" else -1.0) if itm else 0.0
        return Greeks(price=price, delta=delta, gamma=0.0, vega=0.0,
                      theta=0.0, rho=0.0)

    disc_r = np.exp(-r * T)
    disc_q = np.exp(-q * T)
    sqrt_t = np.sqrt(T)
    d1, d2 = _d1_d2(S, K, T, r, sigma, q)
    pdf_d1 = _norm_pdf(d1)

    # Gamma & Vega are identical for calls and puts.
    gamma = disc_q * pdf_d1 / (S * sigma * sqrt_t)
    vega = S * disc_q * pdf_d1 * sqrt_t  # per 1.00 change in sigma

    if kind == "call":
        delta = disc_q * _norm_cdf(d1)
        theta = (
            -S * disc_q * pdf_d1 * sigma / (2.0 * sqrt_t)
            - r * K * disc_r * _norm_cdf(d2)
            + q * S * disc_q * _norm_cdf(d1)
        )
        rho = K * T * disc_r * _norm_cdf(d2)  # per 1.00 change in r
    else:
        delta = -disc_q * _norm_cdf(-d1)
        theta = (
            -S * disc_q * pdf_d1 * sigma / (2.0 * sqrt_t)
            + r * K * disc_r * _norm_cdf(-d2)
            - q * S * disc_q * _norm_cdf(-d1)
        )
        rho = -K * T * disc_r * _norm_cdf(-d2)

    return Greeks(
        price=price,
        delta=float(delta),
        gamma=float(gamma),
        vega=float(vega),
        theta=float(theta),
        rho=float(rho),
    )


# --------------------------------------------------------------------------- #
# Implied volatility
# --------------------------------------------------------------------------- #
def put_call_parity_gap(call, put, S, K, T, r, q=0.0) -> float:
    """
    Residual of the put-call parity identity

        C - P == S e^{-qT} - K e^{-rT}

    A value near zero confirms internal consistency of a call/put pair.
    """
    lhs = call - put
    rhs = S * np.exp(-q * T) - K * np.exp(-r * T)
    return float(lhs - rhs)


def implied_volatility(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    q: float = 0.0,
    kind: OptionKind = "call",
    lo: float = 1e-6,
    hi: float = 10.0,
) -> float:
    """
    Back out the Black-Scholes implied volatility from an observed option price
    using Brent's method (robust, bracketed root-finding).

    Raises ``ValueError`` if the price violates the no-arbitrage bounds so an
    implied vol cannot exist.
    """
    kind = _validate_kind(kind)
    if T <= 0:
        raise ValueError("cannot invert volatility at or after expiry (T<=0)")

    disc_r = np.exp(-r * T)
    disc_q = np.exp(-q * T)
    # No-arbitrage price bounds.
    if kind == "call":
        lower, upper = max(S * disc_q - K * disc_r, 0.0), S * disc_q
    else:
        lower, upper = max(K * disc_r - S * disc_q, 0.0), K * disc_r
    if price < lower - 1e-10 or price > upper + 1e-10:
        raise ValueError(
            f"price {price:.6f} outside no-arbitrage bounds "
            f"[{lower:.6f}, {upper:.6f}] for a {kind}"
        )

    def objective(sig: float) -> float:
        return float(bs_price(S, K, T, r, sig, q, kind)) - price

    f_lo, f_hi = objective(lo), objective(hi)
    if f_lo * f_hi > 0:
        # Price at deep-ITM/OTM extreme; clamp to nearest bound.
        return lo if abs(f_lo) < abs(f_hi) else hi
    return float(brentq(objective, lo, hi, xtol=1e-8, maxiter=200))


# --------------------------------------------------------------------------- #
# Object-oriented convenience wrapper
# --------------------------------------------------------------------------- #
class BlackScholes:
    """
    Thin object wrapper around the functional API for ergonomic reuse.

    >>> bs = BlackScholes(S=100, K=100, T=1, r=0.05, sigma=0.2)
    >>> round(bs.price(), 4)
    10.4506
    >>> bs.greeks().delta
    0.6368...
    """

    def __init__(self, S, K, T, r, sigma, q=0.0, kind: OptionKind = "call"):
        self.params = OptionParams(S=S, K=K, T=T, r=r, sigma=sigma, q=q, kind=kind)

    def _args(self):
        p = self.params
        return p.S, p.K, p.T, p.r, p.sigma, p.q, p.kind

    def price(self) -> float:
        return float(bs_price(*self._args()))

    def greeks(self) -> Greeks:
        return bs_greeks(*self._args())

    def implied_vol(self, observed_price: float) -> float:
        p = self.params
        return implied_volatility(
            observed_price, p.S, p.K, p.T, p.r, p.q, p.kind
        )

    def __repr__(self) -> str:
        p = self.params
        return (
            f"BlackScholes(S={p.S}, K={p.K}, T={p.T}, r={p.r}, "
            f"sigma={p.sigma}, q={p.q}, kind={p.kind!r})"
        )
