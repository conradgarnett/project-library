"""
Multi-leg option strategy analyzer.

Build arbitrary combinations of calls, puts, and the underlying, then get:
  * net premium (debit/credit),
  * aggregate (position-level) Greeks,
  * the payoff / P&L curve at expiry,
  * breakeven point(s), and max profit / max loss over a spot range.

Convenience constructors are provided for common structures (vertical spreads,
straddle, strangle, iron condor, covered call, protective put).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from .black_scholes import bs_greeks, bs_price

LegKind = Literal["call", "put", "underlying"]


@dataclass
class Leg:
    """A single position leg. ``quantity`` > 0 is long, < 0 is short."""

    kind: LegKind
    quantity: float = 1.0
    K: float = 0.0          # ignored for underlying legs

    def price(self, S, T, r, sigma, q=0.0) -> float:
        if self.kind == "underlying":
            return float(S)
        return float(bs_price(S, self.K, T, r, sigma, q, self.kind))

    def payoff(self, S_T: np.ndarray) -> np.ndarray:
        if self.kind == "underlying":
            return S_T
        if self.kind == "call":
            return np.maximum(S_T - self.K, 0.0)
        return np.maximum(self.K - S_T, 0.0)

    def greeks(self, S, T, r, sigma, q=0.0) -> dict:
        if self.kind == "underlying":
            # Underlying: delta 1, everything else 0.
            return {"price": float(S), "delta": 1.0, "gamma": 0.0,
                    "vega": 0.0, "theta": 0.0, "rho": 0.0}
        return bs_greeks(S, self.K, T, r, sigma, q, self.kind).as_dict()


@dataclass
class Strategy:
    """A named collection of legs priced on a common underlying/vol/rate."""

    name: str
    legs: list[Leg] = field(default_factory=list)

    def add(self, kind: LegKind, quantity: float = 1.0, K: float = 0.0) -> "Strategy":
        self.legs.append(Leg(kind=kind, quantity=quantity, K=K))
        return self

    # -- valuation --------------------------------------------------------- #
    def net_premium(self, S, T, r, sigma, q=0.0) -> float:
        """Net cost to open (positive = debit paid, negative = credit received)."""
        return sum(leg.quantity * leg.price(S, T, r, sigma, q) for leg in self.legs)

    def greeks(self, S, T, r, sigma, q=0.0) -> dict:
        """Position-level Greeks (quantity-weighted sum of leg Greeks)."""
        agg = {k: 0.0 for k in ("price", "delta", "gamma", "vega", "theta", "rho")}
        for leg in self.legs:
            g = leg.greeks(S, T, r, sigma, q)
            for k in agg:
                agg[k] += leg.quantity * g[k]
        return agg

    def payoff_at_expiry(self, S_T: np.ndarray) -> np.ndarray:
        total = np.zeros_like(np.asarray(S_T, dtype=float))
        for leg in self.legs:
            total += leg.quantity * leg.payoff(S_T)
        return total

    def pnl_at_expiry(self, S_T, S, T, r, sigma, q=0.0) -> np.ndarray:
        """Payoff minus the net premium paid to open the position."""
        return self.payoff_at_expiry(S_T) - self.net_premium(S, T, r, sigma, q)

    # -- summary ----------------------------------------------------------- #
    def profile(self, S, T, r, sigma, q=0.0, spot_span=0.6, n=801) -> dict:
        """
        Summary over a spot range: max profit / max loss / breakevens / net
        premium / aggregate Greeks. Breakevens are P&L sign changes.
        """
        lo, hi = S * (1 - spot_span), S * (1 + spot_span)
        grid = np.linspace(max(lo, 1e-6), hi, n)
        pnl = self.pnl_at_expiry(grid, S, T, r, sigma, q)

        # Breakevens: linear-interpolate zero crossings of P&L.
        breakevens = []
        sign = np.sign(pnl)
        for i in np.where(np.diff(sign) != 0)[0]:
            x0, x1, y0, y1 = grid[i], grid[i + 1], pnl[i], pnl[i + 1]
            breakevens.append(float(x0 - y0 * (x1 - x0) / (y1 - y0)))

        return {
            "name": self.name,
            "net_premium": self.net_premium(S, T, r, sigma, q),
            "max_profit": float(np.max(pnl)),
            "max_loss": float(np.min(pnl)),
            "breakevens": breakevens,
            "greeks": self.greeks(S, T, r, sigma, q),
            "grid": grid,
            "pnl": pnl,
        }


# --------------------------------------------------------------------------- #
# Common strategy constructors
# --------------------------------------------------------------------------- #
def bull_call_spread(K_long, K_short) -> Strategy:
    return Strategy("Bull call spread").add("call", +1, K_long).add("call", -1, K_short)


def bear_put_spread(K_long, K_short) -> Strategy:
    return Strategy("Bear put spread").add("put", +1, K_long).add("put", -1, K_short)


def straddle(K, long=True) -> Strategy:
    s = 1 if long else -1
    name = "Long straddle" if long else "Short straddle"
    return Strategy(name).add("call", s, K).add("put", s, K)


def strangle(K_put, K_call, long=True) -> Strategy:
    s = 1 if long else -1
    name = "Long strangle" if long else "Short strangle"
    return Strategy(name).add("put", s, K_put).add("call", s, K_call)


def iron_condor(Kp_long, Kp_short, Kc_short, Kc_long) -> Strategy:
    return (
        Strategy("Iron condor")
        .add("put", +1, Kp_long).add("put", -1, Kp_short)
        .add("call", -1, Kc_short).add("call", +1, Kc_long)
    )


def covered_call(K_call) -> Strategy:
    return Strategy("Covered call").add("underlying", +1).add("call", -1, K_call)


def protective_put(K_put) -> Strategy:
    return Strategy("Protective put").add("underlying", +1).add("put", +1, K_put)
