"""
optlib — a compact, well-tested options pricing & risk library.

Modules
-------
black_scholes : closed-form European option pricing + all 5 Greeks + implied vol.
monte_carlo   : risk-neutral Monte-Carlo pricer (GBM) with variance reduction,
                standard errors / confidence intervals, and finite-difference Greeks.
visualize     : matplotlib visualizations (vol smile & surface, Greek curves,
                MC convergence, payoff diagrams, sample paths).

The two pricers share the same parameter convention so their results can be
compared directly (see `optlib.compare`).

Parameter convention (used everywhere)
--------------------------------------
S     : spot price of the underlying
K     : strike price
T     : time to expiry in YEARS
r     : continuously-compounded risk-free rate (e.g. 0.05 for 5%)
sigma : annualised volatility of returns (e.g. 0.20 for 20%)
q     : continuous dividend yield (default 0.0)
kind  : "call" or "put"

Greek units
-----------
delta : per $1 move in S
gamma : per $1 move in S (change in delta)
vega  : per 1.00 change in sigma (i.e. +100 vol points). Divide by 100 for "per vol point".
theta : per YEAR. Divide by 365 for "per calendar day".
rho   : per 1.00 change in r (i.e. +100 bps ×100). Divide by 100 for "per 1%".
"""

from .black_scholes import (
    BlackScholes,
    OptionParams,
    Greeks,
    bs_price,
    bs_greeks,
    implied_volatility,
    put_call_parity_gap,
)
from .monte_carlo import (
    MonteCarloPricer,
    MCResult,
    mc_price,
)
from .binomial import (
    binomial_price,
    binomial_greeks,
)
from .strategy import (
    Strategy,
    Leg,
)

__all__ = [
    "BlackScholes",
    "OptionParams",
    "Greeks",
    "bs_price",
    "bs_greeks",
    "implied_volatility",
    "put_call_parity_gap",
    "MonteCarloPricer",
    "MCResult",
    "mc_price",
    "binomial_price",
    "binomial_greeks",
    "Strategy",
    "Leg",
]

__version__ = "1.0.0"
