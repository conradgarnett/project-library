"""
Exotic (path-dependent and non-vanilla) option pricing.

Covers the workhorse exotics, each with a closed form where one exists and a
Monte-Carlo estimator that cross-checks it:

  digital / binary   cash-or-nothing & asset-or-nothing (closed form, exact)
  geometric Asian    average-price option on the geometric mean (Kemna-Vorst
                     closed form — the geometric average of GBM is lognormal)
  arithmetic Asian   Monte-Carlo with the geometric Asian as a control variate
                     (huge variance reduction since the two are ~perfectly
                     correlated and the control's mean is known exactly)
  barrier            continuously-monitored knock-in / knock-out
                     (Reiner-Rubinstein closed form) + discretely-monitored MC
  lookback           floating-strike lookback via Monte-Carlo

All use the same (S, K, T, r, sigma, q) convention as the rest of the library.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import norm

from .black_scholes import bs_price

N = norm.cdf


# ======================================================================= #
# Digital / binary
# ======================================================================= #
def digital_price(S, K, T, r, sigma, q=0.0, kind="call", style="cash", cash=1.0):
    """
    Closed-form binary option.

    style="cash"  -> cash-or-nothing: pays ``cash`` if it finishes ITM.
    style="asset" -> asset-or-nothing: pays S_T if it finishes ITM.
    """
    kind = kind.lower()
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if style == "cash":
        if kind == "call":
            return float(cash * np.exp(-r * T) * N(d2))
        return float(cash * np.exp(-r * T) * N(-d2))
    elif style == "asset":
        if kind == "call":
            return float(S * np.exp(-q * T) * N(d1))
        return float(S * np.exp(-q * T) * N(-d1))
    raise ValueError("style must be 'cash' or 'asset'")


# ======================================================================= #
# Asian (average price)
# ======================================================================= #
def geometric_asian_price(S, K, T, r, sigma, q=0.0, kind="call"):
    """
    Closed-form continuous geometric-average-price Asian option (Kemna-Vorst).
    Prices by mapping to Black-Scholes with adjusted vol and carry.
    """
    sigma_a = sigma / np.sqrt(3.0)
    b = r - q
    b_a = 0.5 * (b - sigma ** 2 / 6.0)     # adjusted drift of the geometric mean
    q_a = r - b_a                          # implied dividend so (r - q_a) = b_a
    return float(bs_price(S, K, T, r, sigma_a, q_a, kind))


def asian_price_mc(
    S, K, T, r, sigma, q=0.0, kind="call", average="arithmetic",
    n_paths=100_000, n_steps=252, seed=42, control_variate=True,
):
    """
    Monte-Carlo Asian option on the discrete average of the path.

    For the arithmetic average (no closed form) the geometric Asian is used as a
    control variate, since the two payoffs are almost perfectly correlated and
    the geometric price is known exactly. Returns (price, std_error).
    """
    kind = kind.lower()
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    drift = (r - q - 0.5 * sigma ** 2) * dt
    vol = sigma * np.sqrt(dt)

    # Antithetic normal draws.
    half = rng.standard_normal((n_paths // 2 + n_paths % 2, n_steps))
    Z = np.concatenate([half, -half])[:n_paths]
    log_incr = drift + vol * Z
    log_paths = np.cumsum(log_incr, axis=1)
    paths = S * np.exp(log_paths)          # shape (n_paths, n_steps)

    arith = paths.mean(axis=1)
    geo = np.exp(np.log(paths).mean(axis=1))
    disc = np.exp(-r * T)

    def payoff(avg):
        return np.maximum(avg - K, 0.0) if kind == "call" else np.maximum(K - avg, 0.0)

    target = arith if average == "arithmetic" else geo
    discounted = disc * payoff(target)

    if control_variate and average == "arithmetic":
        cv = disc * payoff(geo)
        cv_true = geometric_asian_price(S, K, T, r, sigma, q, kind)
        cov = np.cov(discounted, cv, ddof=1)
        beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0.0
        adjusted = discounted - beta * (cv - cv_true)
    else:
        adjusted = discounted

    price = float(adjusted.mean())
    se = float(adjusted.std(ddof=1) / np.sqrt(n_paths))
    return price, se


# ======================================================================= #
# Barrier (continuously monitored) — Reiner-Rubinstein
# ======================================================================= #
def barrier_price(S, K, H, T, r, sigma, q=0.0, kind="call", barrier_type="down-out"):
    """
    Continuously-monitored single-barrier option (no rebate), closed form.

    barrier_type in {"down-in", "down-out", "up-in", "up-out"}.
    Satisfies in-out parity:  knock-in + knock-out == vanilla.
    """
    kind = kind.lower()
    barrier_type = barrier_type.lower()
    b = r - q
    srt = sigma * np.sqrt(T)
    mu = (b - 0.5 * sigma ** 2) / sigma ** 2
    lam = np.sqrt(mu ** 2 + 2 * r / sigma ** 2)  # noqa: F841 (rebate term unused)
    Dq = np.exp((b - r) * T)
    Dr = np.exp(-r * T)

    phi = 1.0 if kind == "call" else -1.0
    eta = 1.0 if barrier_type.startswith("down") else -1.0

    x1 = np.log(S / K) / srt + (1 + mu) * srt
    x2 = np.log(S / H) / srt + (1 + mu) * srt
    y1 = np.log(H ** 2 / (S * K)) / srt + (1 + mu) * srt
    y2 = np.log(H / S) / srt + (1 + mu) * srt

    A = phi * S * Dq * N(phi * x1) - phi * K * Dr * N(phi * x1 - phi * srt)
    B = phi * S * Dq * N(phi * x2) - phi * K * Dr * N(phi * x2 - phi * srt)
    C = (phi * S * Dq * (H / S) ** (2 * (mu + 1)) * N(eta * y1)
         - phi * K * Dr * (H / S) ** (2 * mu) * N(eta * y1 - eta * srt))
    D = (phi * S * Dq * (H / S) ** (2 * (mu + 1)) * N(eta * y2)
         - phi * K * Dr * (H / S) ** (2 * mu) * N(eta * y2 - eta * srt))

    # Reiner-Rubinstein assembly (Haug); each in/out pair sums to vanilla A.
    K_ge_H = K >= H
    K_gt_H = K > H
    key = (kind, barrier_type)
    if key == ("call", "down-in"):
        val = C if K_ge_H else A - B + D
    elif key == ("call", "down-out"):
        val = A - C if K_ge_H else B - D
    elif key == ("call", "up-in"):
        val = A if K_gt_H else B - C + D
    elif key == ("call", "up-out"):
        val = 0.0 if K_gt_H else A - B + C - D
    elif key == ("put", "down-in"):
        val = B - C + D if K_gt_H else A
    elif key == ("put", "down-out"):
        val = A - B + C - D if K_gt_H else 0.0
    elif key == ("put", "up-in"):
        val = A - B + D if K_gt_H else C
    elif key == ("put", "up-out"):
        val = B - D if K_gt_H else A - C
    else:
        raise ValueError(f"bad barrier_type {barrier_type!r}")

    return float(max(val, 0.0))


def barrier_price_mc(
    S, K, H, T, r, sigma, q=0.0, kind="call", barrier_type="down-out",
    n_paths=100_000, n_steps=252, seed=42, continuity_correction=True,
):
    """
    Discretely-monitored barrier via Monte-Carlo. With the Broadie-Glasserman
    -Kou continuity correction the discrete price closely matches the
    continuous closed form. Returns (price, std_error).
    """
    kind = kind.lower()
    barrier_type = barrier_type.lower()
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    drift = (r - q - 0.5 * sigma ** 2) * dt
    vol = sigma * np.sqrt(dt)

    H_eff = H
    if continuity_correction:
        # Broadie-Glasserman-Kou: to make a discretely-monitored MC approximate
        # the continuously-monitored price, move the barrier *toward* the spot
        # (raise a down-barrier, lower an up-barrier) so the coarser grid knocks
        # out about as often as continuous monitoring would.
        beta = 0.5825971579  # -zeta(1/2)/sqrt(2*pi)
        shift = np.exp(beta * sigma * np.sqrt(dt))
        H_eff = H / shift if barrier_type.startswith("up") else H * shift

    half = rng.standard_normal((n_paths // 2 + n_paths % 2, n_steps))
    Z = np.concatenate([half, -half])[:n_paths]
    paths = S * np.exp(np.cumsum(drift + vol * Z, axis=1))

    if barrier_type.startswith("down"):
        hit = (paths.min(axis=1) <= H_eff)
    else:
        hit = (paths.max(axis=1) >= H_eff)

    S_T = paths[:, -1]
    intrinsic = np.maximum(S_T - K, 0.0) if kind == "call" else np.maximum(K - S_T, 0.0)
    knocked_out = "out" in barrier_type
    alive = (~hit) if knocked_out else hit
    payoff = np.where(alive, intrinsic, 0.0)

    disc = np.exp(-r * T)
    discounted = disc * payoff
    return float(discounted.mean()), float(discounted.std(ddof=1) / np.sqrt(n_paths))


# ======================================================================= #
# Lookback (floating strike) — Monte-Carlo
# ======================================================================= #
def lookback_price_mc(
    S, T, r, sigma, q=0.0, kind="call", n_paths=100_000, n_steps=252, seed=42,
):
    """
    Floating-strike lookback via Monte-Carlo.
      call payoff = S_T - min(path)   (buy at the lowest price seen)
      put  payoff = max(path) - S_T   (sell at the highest price seen)
    Returns (price, std_error).
    """
    kind = kind.lower()
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    drift = (r - q - 0.5 * sigma ** 2) * dt
    vol = sigma * np.sqrt(dt)

    half = rng.standard_normal((n_paths // 2 + n_paths % 2, n_steps))
    Z = np.concatenate([half, -half])[:n_paths]
    paths = S * np.exp(np.cumsum(drift + vol * Z, axis=1))
    paths = np.hstack([np.full((paths.shape[0], 1), float(S)), paths])
    S_T = paths[:, -1]

    if kind == "call":
        payoff = S_T - paths.min(axis=1)
    else:
        payoff = paths.max(axis=1) - S_T

    disc = np.exp(-r * T)
    discounted = disc * payoff
    return float(discounted.mean()), float(discounted.std(ddof=1) / np.sqrt(n_paths))
