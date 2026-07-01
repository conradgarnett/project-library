"""
Matplotlib visualizations for the pricing library.

Every function returns a ``matplotlib.figure.Figure`` and, if ``save_path`` is
given, also writes a PNG. Nothing calls ``plt.show()`` so the module works
headlessly (e.g. in CI or when generating a report).

Figures
-------
plot_greeks_vs_spot   : all five Greeks as the spot ranges over the strike.
plot_vol_smile        : implied-vol smile/skew across strikes.
plot_vol_surface      : 3-D implied-vol surface over (strike, maturity).
plot_mc_convergence   : MC price estimate + CI band converging to the BS price.
plot_payoff_diagram   : payoff & P/L at expiry for the option.
plot_sample_paths     : simulated GBM paths with the terminal histogram.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless backend; safe everywhere
import matplotlib.pyplot as plt
import numpy as np

from .black_scholes import bs_greeks, bs_price
from .compare import convergence_table
from .monte_carlo import MonteCarloPricer


def _finish(fig, save_path):
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=130, bbox_inches="tight")
    return fig


# --------------------------------------------------------------------------- #
def plot_greeks_vs_spot(
    K, T, r, sigma, q=0.0, kind="call",
    spot_range=None, save_path=None,
):
    """Plot price + the five Greeks as functions of spot."""
    if spot_range is None:
        spot_range = np.linspace(0.4 * K, 1.6 * K, 240)

    metrics = {k: [] for k in ("price", "delta", "gamma", "vega", "theta", "rho")}
    for S in spot_range:
        g = bs_greeks(S, K, T, r, sigma, q, kind)
        for k in metrics:
            metrics[k].append(getattr(g, k))

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    titles = {
        "price": "Price",
        "delta": "Delta  (∂V/∂S)",
        "gamma": "Gamma  (∂²V/∂S²)",
        "vega": "Vega  (∂V/∂σ, per 1.00 vol)",
        "theta": "Theta  (∂V/∂t, per year)",
        "rho": "Rho  (∂V/∂r, per 1.00 rate)",
    }
    for ax, (k, title) in zip(axes.ravel(), titles.items()):
        ax.plot(spot_range, metrics[k], color="#1f77b4", lw=2)
        ax.axvline(K, color="grey", ls="--", lw=1, alpha=0.7, label="strike")
        ax.set_title(title)
        ax.set_xlabel("Spot  S")
        ax.grid(alpha=0.3)
        ax.legend(loc="best", fontsize=8)
    fig.suptitle(
        f"Black-Scholes {kind.upper()}  —  K={K}, T={T}y, r={r:.2%}, σ={sigma:.2%}",
        fontsize=14, y=1.02,
    )
    return _finish(fig, save_path)


# --------------------------------------------------------------------------- #
def _synthetic_smile(strikes, S, atm_vol=0.20, skew=-0.15, curv=0.6):
    """A plausible equity-style vol smile as a function of log-moneyness."""
    m = np.log(strikes / S)
    return atm_vol + skew * m + curv * m ** 2


def plot_vol_smile(
    S=100.0, strikes=None, atm_vol=0.20, skew=-0.15, curv=0.6, save_path=None,
):
    """
    Plot an implied-volatility smile/skew across strikes. By default it draws a
    synthetic equity skew; pass your own ``strikes``/params to shape it.
    """
    if strikes is None:
        strikes = np.linspace(0.6 * S, 1.4 * S, 60)
    iv = _synthetic_smile(strikes, S, atm_vol, skew, curv)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(strikes, iv * 100, color="#d62728", lw=2)
    ax.axvline(S, color="grey", ls="--", lw=1, label="spot (ATM)")
    ax.set_title("Implied Volatility Smile / Skew")
    ax.set_xlabel("Strike  K")
    ax.set_ylabel("Implied volatility  (%)")
    ax.grid(alpha=0.3)
    ax.legend()
    return _finish(fig, save_path)


def plot_vol_surface(
    S=100.0, strikes=None, maturities=None,
    atm_vol=0.20, skew=-0.15, curv=0.6, term=0.05, save_path=None,
):
    """
    3-D implied-vol surface over (strike, maturity). Term structure adds a mild
    upward slope in maturity on top of the strike smile.
    """
    if strikes is None:
        strikes = np.linspace(0.6 * S, 1.4 * S, 40)
    if maturities is None:
        maturities = np.linspace(0.08, 2.0, 40)

    KK, TT = np.meshgrid(strikes, maturities)
    smile = _synthetic_smile(KK, S, atm_vol, skew, curv)
    IV = (smile + term * np.sqrt(TT)) * 100

    fig = plt.figure(figsize=(11, 7.5))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_surface(KK, TT, IV, cmap="viridis", edgecolor="none", alpha=0.95)
    ax.set_title("Implied Volatility Surface")
    ax.set_xlabel("Strike  K")
    ax.set_ylabel("Maturity  T (yrs)")
    ax.set_zlabel("Implied vol (%)")
    ax.view_init(elev=26, azim=-58)
    fig.colorbar(surf, shrink=0.55, aspect=14, label="IV (%)")
    return _finish(fig, save_path)


# --------------------------------------------------------------------------- #
def plot_mc_convergence(
    S, K, T, r, sigma, q=0.0, kind="call",
    path_counts=(1_000, 5_000, 25_000, 100_000, 500_000, 2_000_000),
    seed=42, save_path=None,
):
    """Plot MC price ± 95% CI vs #paths, converging to the analytic BS price."""
    df = convergence_table(S, K, T, r, sigma, q, kind, path_counts, seed)
    truth = df["bs_price"].iloc[0]

    fig, ax = plt.subplots(figsize=(10, 6))
    yerr = 1.96 * df["std_error"]
    ax.errorbar(
        df["n_paths"], df["mc_price"], yerr=yerr, fmt="o-", capsize=4,
        color="#2ca02c", label="Monte-Carlo ± 95% CI",
    )
    ax.axhline(truth, color="#d62728", ls="--", lw=2, label=f"Black-Scholes = {truth:.4f}")
    ax.set_xscale("log")
    ax.set_title(f"Monte-Carlo convergence to Black-Scholes  ({kind})")
    ax.set_xlabel("Number of simulated paths (log scale)")
    ax.set_ylabel("Option price")
    ax.grid(alpha=0.3, which="both")
    ax.legend()
    return _finish(fig, save_path)


# --------------------------------------------------------------------------- #
def plot_payoff_diagram(
    S, K, T, r, sigma, q=0.0, kind="call", save_path=None,
):
    """Payoff at expiry and current-value curve, with breakeven & P/L shading."""
    spots = np.linspace(0.4 * K, 1.6 * K, 300)
    premium = float(bs_price(S, K, T, r, sigma, q, kind))
    if kind == "call":
        payoff = np.maximum(spots - K, 0.0)
        breakeven = K + premium
    else:
        payoff = np.maximum(K - spots, 0.0)
        breakeven = K - premium
    pnl = payoff - premium
    value_now = np.array([bs_price(s, K, T, r, sigma, q, kind) for s in spots])

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(spots, payoff, color="#1f77b4", lw=2, label="Payoff at expiry")
    ax.plot(spots, pnl, color="#ff7f0e", lw=2, ls="--", label="P/L at expiry (net of premium)")
    ax.plot(spots, value_now, color="#9467bd", lw=1.5, alpha=0.8, label="Value today (BS)")
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(K, color="grey", ls=":", label=f"strike = {K}")
    ax.axvline(breakeven, color="green", ls=":", label=f"breakeven = {breakeven:.2f}")
    ax.fill_between(spots, pnl, 0, where=pnl > 0, color="green", alpha=0.12)
    ax.fill_between(spots, pnl, 0, where=pnl < 0, color="red", alpha=0.12)
    ax.set_title(f"{kind.upper()} option payoff / P&L  (premium={premium:.2f})")
    ax.set_xlabel("Underlying at expiry")
    ax.set_ylabel("Profit / Loss")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    return _finish(fig, save_path)


# --------------------------------------------------------------------------- #
def plot_strategy_pnl(strategy, S, T, r, sigma, q=0.0, save_path=None):
    """
    Plot the expiry P&L of a multi-leg :class:`optlib.strategy.Strategy`, with
    breakevens, max profit/loss, and profit/loss shading.
    """
    prof = strategy.profile(S, T, r, sigma, q)
    grid, pnl = prof["grid"], prof["pnl"]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(grid, pnl, color="#1f77b4", lw=2, label="P&L at expiry")
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(S, color="grey", ls=":", label=f"spot = {S}")
    ax.fill_between(grid, pnl, 0, where=pnl > 0, color="green", alpha=0.12)
    ax.fill_between(grid, pnl, 0, where=pnl < 0, color="red", alpha=0.12)
    for be in prof["breakevens"]:
        ax.axvline(be, color="green", ls="--", lw=1, alpha=0.7)
        ax.annotate(f"BE {be:.1f}", (be, 0), textcoords="offset points",
                    xytext=(3, 8), fontsize=8, color="green")
    g = prof["greeks"]
    subtitle = (f"net premium={prof['net_premium']:.2f}  |  "
                f"max P={prof['max_profit']:.2f}  max L={prof['max_loss']:.2f}  |  "
                f"Δ={g['delta']:.2f} Γ={g['gamma']:.3f} "
                f"V={g['vega'] / 100:.2f} Θ={g['theta'] / 365:.3f}")
    ax.set_title(f"{prof['name']}\n{subtitle}", fontsize=11)
    ax.set_xlabel("Underlying at expiry")
    ax.set_ylabel("Profit / Loss")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    return _finish(fig, save_path)


def plot_sample_paths(
    S, K, T, r, sigma, q=0.0, kind="call",
    n_paths=200, n_steps=252, seed=7, save_path=None,
):
    """Simulated GBM paths + terminal-price histogram vs the strike."""
    pricer = MonteCarloPricer(seed=seed)
    paths = pricer.simulate_paths(S, T, r, sigma, q, n_paths, n_steps, seed=seed)
    t = np.linspace(0, T, n_steps + 1)
    terminal = paths[:, -1]

    fig, (ax1, ax2) = plt.subplots(
        1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [3, 1]}, sharey=True
    )
    ax1.plot(t, paths.T, lw=0.6, alpha=0.35, color="#1f77b4")
    ax1.axhline(K, color="#d62728", ls="--", lw=1.5, label=f"strike = {K}")
    ax1.set_title(f"{n_paths} simulated GBM paths  (σ={sigma:.0%}, T={T}y)")
    ax1.set_xlabel("time (yrs)")
    ax1.set_ylabel("underlying price")
    ax1.legend()
    ax1.grid(alpha=0.3)

    ax2.hist(terminal, bins=45, orientation="horizontal", color="#1f77b4", alpha=0.7)
    ax2.axhline(K, color="#d62728", ls="--", lw=1.5)
    ax2.set_title("terminal S_T")
    ax2.set_xlabel("frequency")
    ax2.grid(alpha=0.3)
    return _finish(fig, save_path)
