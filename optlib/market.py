"""
Market data + volatility-smile calibration.

Two halves:

1. **Live option chains** (optional, needs ``yfinance`` + network): pull a real
   chain, take mid prices, and invert each into a Black-Scholes implied vol with
   the library's own solver — giving the *actual* market smile.

2. **Calibration** (pure, offline-testable): fit a smile with
     * **SVI** (raw Gatheral parameterization) — a flexible, near-arbitrage-free
       fit of total implied variance, the industry-standard smile interpolator;
     * **Merton jump-diffusion** — a structural fit whose parameters
       (jump intensity/size) have economic meaning.

The calibration functions take plain ``(strikes, implied_vols)`` arrays, so they
work on live *or* synthetic smiles and are unit-tested by recovering a known
model's parameters.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from .black_scholes import bs_price, implied_volatility
from .models import merton_jump_price


# ======================================================================= #
# Live option chain (optional dependency)
# ======================================================================= #
def fetch_option_chain(ticker: str, expiry_index: int = 1, kind: str = "call",
                       r: float = 0.045) -> dict:
    """
    Fetch a live option chain via yfinance and compute a clean implied-vol smile.

    Returns a dict with the spot ``S``, time to expiry ``T``, rate ``r``, and a
    DataFrame (strike, mid, iv) filtered to liquid, near-the-money quotes.

    Raises a clear error if yfinance / network is unavailable — callers that want
    an offline fallback should catch it and use :func:`synthetic_smile`.
    """
    try:
        import yfinance as yf
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("yfinance not installed; use synthetic_smile() offline") from e

    tk = yf.Ticker(ticker)
    expiries = tk.options
    if not expiries:
        raise RuntimeError(f"no listed expiries for {ticker}")
    expiry = expiries[min(expiry_index, len(expiries) - 1)]
    chain = tk.option_chain(expiry)
    df = (chain.calls if kind == "call" else chain.puts).copy()

    try:
        S = float(tk.fast_info["lastPrice"])
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"could not read spot for {ticker}") from e

    days = (pd.Timestamp(expiry).normalize() - pd.Timestamp.today().normalize()).days
    T = max(days, 1) / 365.0

    df = df[(df["bid"] > 0) & (df["ask"] > 0)]
    df["mid"] = 0.5 * (df["bid"] + df["ask"])
    # Keep near-the-money strikes where quotes are reliable.
    df = df[(df["strike"] > 0.7 * S) & (df["strike"] < 1.3 * S)]

    ivs = []
    for K, mid in zip(df["strike"], df["mid"]):
        try:
            ivs.append(implied_volatility(float(mid), S, float(K), T, r, 0.0, kind))
        except Exception:
            ivs.append(np.nan)
    df["iv"] = ivs
    df = df.dropna(subset=["iv"])
    df = df[(df["iv"] > 0.01) & (df["iv"] < 3.0)]
    return {"ticker": ticker, "expiry": expiry, "S": S, "T": T, "r": r,
            "kind": kind, "smile": df[["strike", "mid", "iv"]].reset_index(drop=True)}


def synthetic_smile(S=100.0, T=0.5, r=0.045, n=15,
                    sigma=0.2, lam=1.0, muJ=-0.12, sigJ=0.15):
    """
    Build a realistic synthetic smile from a Merton model (no network needed).
    Returns (strikes, implied_vols) — useful for offline demos and tests.
    """
    strikes = np.linspace(0.75 * S, 1.25 * S, n)
    ivs = []
    for K in strikes:
        p = merton_jump_price(S, K, T, r, sigma, 0.0, "call", lam=lam, muJ=muJ, sigJ=sigJ)
        ivs.append(implied_volatility(p, S, K, T, r, 0.0, "call"))
    return strikes, np.array(ivs)


# ======================================================================= #
# SVI (raw Gatheral) calibration
# ======================================================================= #
@dataclass
class SVIParams:
    a: float
    b: float
    rho: float
    m: float
    sigma: float

    def total_variance(self, k):
        """Total implied variance w(k) = σ_BS² · T at log-moneyness k."""
        k = np.asarray(k, dtype=float)
        return self.a + self.b * (self.rho * (k - self.m)
                                  + np.sqrt((k - self.m) ** 2 + self.sigma ** 2))

    def implied_vol(self, k, T):
        return np.sqrt(np.maximum(self.total_variance(k), 1e-12) / T)


def calibrate_svi(strikes, implied_vols, S, T) -> SVIParams:
    """
    Fit the raw SVI parameterization to a smile by least squares on total
    variance. Returns the fitted :class:`SVIParams`.
    """
    strikes = np.asarray(strikes, dtype=float)
    iv = np.asarray(implied_vols, dtype=float)
    k = np.log(strikes / S)
    w = iv ** 2 * T

    def resid(p):
        a, b, rho, m, sig = p
        model = a + b * (rho * (k - m) + np.sqrt((k - m) ** 2 + sig ** 2))
        return model - w

    x0 = [np.min(w), 0.1, -0.3, 0.0, 0.1]
    lb = [-1.0, 0.0, -0.999, -1.0, 1e-4]
    ub = [1.0, 5.0, 0.999, 1.0, 1.0]
    sol = least_squares(resid, x0, bounds=(lb, ub), max_nfev=5000)
    return SVIParams(*sol.x)


# ======================================================================= #
# Merton structural calibration
# ======================================================================= #
@dataclass
class MertonParams:
    sigma: float
    lam: float
    muJ: float
    sigJ: float

    def implied_vol(self, strikes, S, T, r):
        out = []
        for K in np.atleast_1d(strikes):
            p = merton_jump_price(S, K, T, r, self.sigma, 0.0, "call",
                                  lam=self.lam, muJ=self.muJ, sigJ=self.sigJ)
            out.append(implied_volatility(p, S, float(K), T, r, 0.0, "call"))
        return np.array(out)


def calibrate_merton(strikes, implied_vols, S, T, r) -> MertonParams:
    """
    Fit Merton jump-diffusion parameters (σ, λ, μ_J, σ_J) so the model implied
    vols match the market smile (least squares on IV). Returns MertonParams.
    """
    strikes = np.asarray(strikes, dtype=float)
    iv = np.asarray(implied_vols, dtype=float)

    def resid(p):
        sigma, lam, muJ, sigJ = p
        model = []
        for K in strikes:
            price = merton_jump_price(S, K, T, r, sigma, 0.0, "call",
                                      lam=lam, muJ=muJ, sigJ=sigJ)
            model.append(implied_volatility(price, S, float(K), T, r, 0.0, "call"))
        return np.array(model) - iv

    x0 = [np.median(iv) * 0.8, 1.0, -0.1, 0.15]
    lb = [0.01, 0.0, -1.0, 1e-3]
    ub = [2.0, 10.0, 1.0, 1.0]
    sol = least_squares(resid, x0, bounds=(lb, ub), max_nfev=400)
    return MertonParams(*sol.x)


def calibration_rmse(params, strikes, market_ivs, S, T, r=0.045) -> float:
    """Root-mean-square implied-vol error of a fitted smile model, in vol points."""
    strikes = np.asarray(strikes, dtype=float)
    market_ivs = np.asarray(market_ivs, dtype=float)
    if isinstance(params, SVIParams):
        model = params.implied_vol(np.log(strikes / S), T)
    elif isinstance(params, MertonParams):
        model = params.implied_vol(strikes, S, T, r)
    else:
        raise TypeError("params must be SVIParams or MertonParams")
    return float(np.sqrt(np.mean((model - market_ivs) ** 2)))
