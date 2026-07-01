"""
Implied vs realized: relating the model's *implied* quantities to what actually
happens in the underlying.

Implied volatility is the one Black-Scholes input that is inverted from the
market price rather than observed. Once you have it, the Greeks are computed
*at* that implied vol — so the desk's Greeks are already "implied Greeks."
There is no separate inversion for delta/gamma/etc. because IV uses up the
single free degree of freedom. What you *can* additionally extract from prices:

  * implied ITM probability      N(d2)  ==  -e^{rT}·dual_delta   (risk-neutral Q)
  * implied risk-neutral density  e^{rT}·∂²C/∂K²  (Breeden-Litzenberger)
  * the variance risk premium     IV vs realized vol
  * the gamma-theta breakeven     delta-hedged P&L vs realized variance

This module provides all four, so implied model outputs can be fact-checked
against realized volatility.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from .black_scholes import bs_greeks, bs_price

N = norm.cdf


# ======================================================================= #
# Realized volatility estimators
# ======================================================================= #
def realized_volatility(prices, periods_per_year: int = 252, method: str = "close"):
    """
    Annualized realized volatility from a price series.

    method="close" : close-to-close log-return standard deviation (default).
    method="parkinson" : Parkinson high-low estimator; ``prices`` must be an
        (n, 2) array of [high, low] rows (more efficient when you have OHLC).
    """
    prices = np.asarray(prices, dtype=float)
    if method == "close":
        rets = np.diff(np.log(prices))
        return float(np.std(rets, ddof=1) * np.sqrt(periods_per_year))
    if method == "parkinson":
        hi, lo = prices[:, 0], prices[:, 1]
        hl = np.log(hi / lo) ** 2
        var = hl.mean() / (4.0 * np.log(2.0))
        return float(np.sqrt(var * periods_per_year))
    raise ValueError("method must be 'close' or 'parkinson'")


# ======================================================================= #
# Implied (risk-neutral) probabilities
# ======================================================================= #
def implied_prob_itm(S, K, T, r, sigma, q=0.0, kind="call", measure="risk-neutral", mu=None):
    """
    Probability the option finishes in the money.

    measure="risk-neutral" (default): uses drift r-q  → N(d2) for a call.
        This is exactly -e^{rT}·dual_delta.
    measure="real-world": pass the physical expected return ``mu`` (drift μ-q).
        The gap between the two probabilities is the risk premium / the effect
        of the change of measure ℚ→ℙ.
    """
    kind = kind.lower()
    drift = (r if measure == "risk-neutral" else mu)
    if drift is None:
        raise ValueError("real-world measure requires mu (expected return)")
    d2 = (np.log(S / K) + (drift - q - 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    return float(N(d2) if kind == "call" else N(-d2))


# ======================================================================= #
# Breeden-Litzenberger: implied risk-neutral density from call prices
# ======================================================================= #
def risk_neutral_density(strikes, call_prices, r, T):
    """
    Extract the implied risk-neutral density of S_T from a strike-continuum of
    call prices:  f(K) = e^{rT} · ∂²C/∂K²  (Breeden-Litzenberger, 1978).

    ``strikes`` must be sorted ascending and (ideally) evenly spaced. Returns
    (mid_strikes, density) — density is defined on the interior strikes.
    """
    strikes = np.asarray(strikes, dtype=float)
    call_prices = np.asarray(call_prices, dtype=float)
    dK = np.diff(strikes)
    # Second derivative via central differences on the interior points.
    d2C = (call_prices[2:] - 2 * call_prices[1:-1] + call_prices[:-2]) / (dK[:-1] * dK[1:])
    density = np.exp(r * T) * d2C
    return strikes[1:-1], np.maximum(density, 0.0)


def implied_density_from_model(S, K_center, T, r, sigma, q=0.0, width=0.6, n=201):
    """
    Sanity helper: build call prices from our own BS model across strikes and
    recover the density via Breeden-Litzenberger. It should reproduce the known
    lognormal terminal density — a self-consistency check of both routines.
    """
    strikes = np.linspace(S * (1 - width), S * (1 + width), n)
    calls = np.array([bs_price(S, k, T, r, sigma, q, "call") for k in strikes])
    return risk_neutral_density(strikes, calls, r, T)


# ======================================================================= #
# Variance risk premium
# ======================================================================= #
@dataclass(frozen=True)
class VarianceRiskPremium:
    implied_vol: float
    realized_vol: float
    vrp_vol_points: float      # implied - realized, in vol points
    vrp_variance: float        # implied² - realized²


def variance_risk_premium(implied_vol: float, realized_vol: float) -> VarianceRiskPremium:
    """
    Compare the implied vol (the market's forecast) with the realized vol that
    actually occurred over the option's life. A positive premium means options
    were 'rich' — selling vol and delta-hedging was, ex-post, profitable.
    """
    return VarianceRiskPremium(
        implied_vol=implied_vol,
        realized_vol=realized_vol,
        vrp_vol_points=implied_vol - realized_vol,
        vrp_variance=implied_vol ** 2 - realized_vol ** 2,
    )


# ======================================================================= #
# Gamma-theta breakeven + delta-hedging P&L vs realized vol
# ======================================================================= #
def breakeven_move(S, sigma_implied, dt=1.0 / 252.0):
    """
    The daily underlying move at which a delta-hedged option breaks even:
    gamma gains exactly offset theta decay. Equals S·σ_impl·√dt.
    Realized moves larger than this make a long-gamma position profitable.
    """
    return float(S * sigma_implied * np.sqrt(dt))


def delta_hedge_pnl(
    S, K, T, r, sigma_implied, sigma_realized, q=0.0, kind="call", position="long",
    n_steps=252, n_paths=20_000, seed=42,
):
    """
    Simulate delta-hedging an option to expiry to fact-check the gamma-theta
    identity. The option is priced and hedged at ``sigma_implied`` while the
    underlying actually realizes ``sigma_realized``.

    Per step the vol P&L of the delta-hedged position is
        ½ · Γ(σ_impl) · S² · ((ΔS/S)² − σ_impl²·dt),
    which in expectation is ½·Γ·S²·(σ_realized² − σ_impl²)·dt. So a *long*
    option makes money exactly when realized variance exceeds implied.

    Returns a dict with the simulated mean P&L ± standard error, the closed-form
    prediction, and the two vols — the concrete link between implied Greeks and
    realized volatility.
    """
    kind = kind.lower()
    sign = 1.0 if position == "long" else -1.0
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    drift = (r - q - 0.5 * sigma_realized ** 2) * dt
    vol = sigma_realized * np.sqrt(dt)

    half = rng.standard_normal((n_paths // 2 + n_paths % 2, n_steps))
    Z = np.concatenate([half, -half])[:n_paths]
    log_incr = drift + vol * Z
    S_path = np.empty((n_paths, n_steps + 1))
    S_path[:, 0] = S
    S_path[:, 1:] = S * np.exp(np.cumsum(log_incr, axis=1))

    pnl = np.zeros(n_paths)
    gamma_S2_sum = np.zeros(n_paths)  # for the prediction
    for t in range(n_steps):
        St = S_path[:, t]
        tau = T - t * dt
        # gamma at implied vol, vectorised (same formula as bs_greeks.gamma)
        d1 = (np.log(St / K) + (r - q + 0.5 * sigma_implied ** 2) * tau) / (
            sigma_implied * np.sqrt(tau))
        gamma = np.exp(-q * tau) * norm.pdf(d1) / (St * sigma_implied * np.sqrt(tau))
        dS = S_path[:, t + 1] - St
        step_pnl = 0.5 * gamma * (dS ** 2 - (sigma_implied ** 2) * (St ** 2) * dt)
        pnl += step_pnl
        gamma_S2_sum += gamma * St ** 2 * dt

    pnl *= sign
    prediction = sign * 0.5 * (sigma_realized ** 2 - sigma_implied ** 2) * gamma_S2_sum
    return {
        "mean_pnl": float(pnl.mean()),
        "std_error": float(pnl.std(ddof=1) / np.sqrt(n_paths)),
        "predicted_pnl": float(prediction.mean()),
        "sigma_implied": sigma_implied,
        "sigma_realized": sigma_realized,
        "position": position,
    }
