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

from .binomial import binomial_price
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
def plot_model_convergence(
    S, K, T, r, sigma, q=0.0, kind="call",
    mc_counts=(1_000, 5_000, 25_000, 100_000, 500_000, 2_000_000),
    tree_steps=(5, 10, 25, 50, 100, 250, 500, 1000, 2000),
    seed=42, save_path=None,
):
    """
    Side-by-side view of *both* numerical methods homing in on the analytic
    Black-Scholes price: Monte-Carlo (± 95% CI) vs the binomial tree.
    """
    truth = float(bs_price(S, K, T, r, sigma, q, kind))

    mc_px, mc_se = [], []
    for n in mc_counts:
        res = MonteCarloPricer(n_paths=n, seed=seed).price(S, K, T, r, sigma, q, kind)
        mc_px.append(res.price)
        mc_se.append(res.std_error)
    tree_px = [binomial_price(S, K, T, r, sigma, q, kind, "european", n) for n in tree_steps]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    ax1.errorbar(mc_counts, mc_px, yerr=1.96 * np.array(mc_se), fmt="o-",
                 capsize=4, color="#2ca02c", label="Monte-Carlo ± 95% CI")
    ax1.axhline(truth, color="#d62728", ls="--", lw=2, label=f"BS = {truth:.4f}")
    ax1.set_xscale("log")
    ax1.set_title("Monte-Carlo convergence")
    ax1.set_xlabel("paths (log)")
    ax1.set_ylabel("price")
    ax1.grid(alpha=0.3, which="both")
    ax1.legend()

    ax2.plot(tree_steps, tree_px, "o-", color="#1f77b4", label="Binomial tree")
    ax2.axhline(truth, color="#d62728", ls="--", lw=2, label=f"BS = {truth:.4f}")
    ax2.set_xscale("log")
    ax2.set_title("Binomial tree convergence")
    ax2.set_xlabel("steps (log)")
    ax2.set_ylabel("price")
    ax2.grid(alpha=0.3, which="both")
    ax2.legend()

    fig.suptitle(f"Numerical pricers → Black-Scholes  ({kind})", fontsize=13, y=1.02)
    return _finish(fig, save_path)


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
def plot_scenario_heatmap(scenario_result, metric="pnl", S0=None, title=None, save_path=None):
    """
    Heatmap of a scenario/risk grid metric over spot (x) × vol (y).
    ``scenario_result`` is the object returned by ``optlib.scenario.scenario_grid``.
    """
    res = scenario_result
    Z = res.metrics[metric]
    fig, ax = plt.subplots(figsize=(11, 6.5))
    diverging = metric in ("pnl", "delta", "theta", "rho")
    cmap = "RdYlGn" if diverging else "viridis"
    vmax = np.abs(Z).max() if diverging else None
    vmin = -vmax if diverging else None
    im = ax.imshow(Z, origin="lower", aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax,
                   extent=[res.spots[0], res.spots[-1],
                           res.vols[0] * 100, res.vols[-1] * 100])
    if S0 is not None:
        ax.axvline(S0, color="black", ls=":", lw=1, alpha=0.6, label="spot $S_0$")
        ax.legend(loc="upper left")
    fig.colorbar(im, ax=ax, label=metric)
    ax.set_title(title or f"Scenario {metric} — spot × volatility"
                 f"  (T_eval={res.T_eval:.3f}y)")
    ax.set_xlabel("underlying spot")
    ax.set_ylabel("volatility (%)")
    return _finish(fig, save_path)


def plot_market_smile(strikes, market_ivs, fitted=None, S=None, title=None, save_path=None):
    """
    Plot a market implied-vol smile (points), optionally with one or more fitted
    curves overlaid. ``fitted`` is a dict {label: iv_array} aligned to ``strikes``.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(strikes, np.asarray(market_ivs) * 100, s=28, color="#333333",
               zorder=3, label="market IV")
    if fitted:
        colors = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd"]
        for (label, iv), c in zip(fitted.items(), colors):
            ax.plot(strikes, np.asarray(iv) * 100, lw=2, color=c, label=label)
    if S is not None:
        ax.axvline(S, color="grey", ls=":", label="spot")
    ax.set_title(title or "Market implied-volatility smile")
    ax.set_xlabel("strike K")
    ax.set_ylabel("implied volatility (%)")
    ax.grid(alpha=0.3)
    ax.legend()
    return _finish(fig, save_path)


def plot_risk_neutral_density(S, K_center, T, r, sigma, q=0.0, save_path=None):
    """
    The implied risk-neutral density recovered from model call prices via
    Breeden-Litzenberger (e^{rT}·∂²C/∂K²), overlaid with the exact lognormal
    terminal density — showing what "implied distribution" means.
    """
    from scipy.stats import norm as _norm

    from .implied import implied_density_from_model

    mids, dens = implied_density_from_model(S, K_center, T, r, sigma, q, width=0.8, n=401)
    # Exact lognormal density of S_T under the risk-neutral measure.
    m = np.log(S) + (r - q - 0.5 * sigma ** 2) * T
    s = sigma * np.sqrt(T)
    exact = _norm.pdf((np.log(mids) - m) / s) / (mids * s)

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(mids, dens, color="#1f77b4", lw=2, label="implied density (Breeden-Litzenberger)")
    ax.plot(mids, exact, color="#d62728", lw=1.5, ls="--", label="exact lognormal density")
    ax.axvline(S * np.exp((r - q) * T), color="grey", ls=":", label="forward")
    ax.set_title(f"Implied risk-neutral density of $S_T$  (T={T}y, σ={sigma:.0%})")
    ax.set_xlabel("terminal price $S_T$")
    ax.set_ylabel("probability density")
    ax.grid(alpha=0.3)
    ax.legend()
    return _finish(fig, save_path)


def plot_iv_vs_realized_hedge(
    S, K, T, r, sigma_implied, q=0.0, kind="call",
    realized_vols=None, n_paths=20_000, save_path=None,
):
    """
    Fact-check the gamma-theta identity: mean delta-hedged P&L of a *long*
    option (priced/hedged at implied vol) as a function of the *realized* vol.
    The curve crosses zero exactly where realized == implied — money is made
    only when the underlying moves more than the option implied.
    """
    from .implied import delta_hedge_pnl

    if realized_vols is None:
        realized_vols = np.linspace(0.5 * sigma_implied, 1.6 * sigma_implied, 13)
    means, ses, preds = [], [], []
    for rv in realized_vols:
        res = delta_hedge_pnl(S, K, T, r, sigma_implied, rv, q, kind,
                              "long", n_steps=126, n_paths=n_paths)
        means.append(res["mean_pnl"])
        ses.append(res["std_error"])
        preds.append(res["predicted_pnl"])

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.errorbar(np.array(realized_vols) * 100, means, yerr=1.96 * np.array(ses),
                fmt="o", capsize=4, color="#2ca02c", label="simulated hedged P&L ± 95% CI")
    ax.plot(np.array(realized_vols) * 100, preds, color="#1f77b4", lw=2,
            label="gamma-theta prediction")
    ax.axhline(0, color="black", lw=0.8)
    ax.axvline(sigma_implied * 100, color="#d62728", ls="--",
               label=f"implied vol = {sigma_implied:.0%}")
    ax.set_title("Delta-hedged long-option P&L vs realized volatility\n"
                 "(you profit only when realized > implied)")
    ax.set_xlabel("realized volatility (%)")
    ax.set_ylabel("mean hedged P&L")
    ax.grid(alpha=0.3)
    ax.legend()
    return _finish(fig, save_path)


def plot_model_smiles(S=100.0, T=1.0, r=0.05, q=0.0, save_path=None):
    """
    Implied-vol smiles that Black-Scholes cannot produce but Merton jump
    -diffusion and Heston stochastic vol generate endogenously.
    """
    from .black_scholes import implied_volatility
    from .models import heston_price_mc, merton_jump_price

    strikes = np.linspace(0.7 * S, 1.3 * S, 25)
    base_sigma = 0.2

    merton_iv, heston_iv = [], []
    for Kx in strikes:
        pm = merton_jump_price(S, Kx, T, r, base_sigma, q, "call",
                               lam=1.0, muJ=-0.12, sigJ=0.15)
        merton_iv.append(implied_volatility(pm, S, Kx, T, r, q, "call"))
        ph, _ = heston_price_mc(S, Kx, T, r, q, "call", v0=base_sigma ** 2,
                                kappa=2.0, theta=base_sigma ** 2, xi=0.5, rho=-0.7,
                                n_paths=150_000, n_steps=150)
        heston_iv.append(implied_volatility(ph, S, Kx, T, r, q, "call"))

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(strikes, np.array(merton_iv) * 100, "o-", color="#1f77b4",
            label="Merton jump-diffusion")
    ax.plot(strikes, np.array(heston_iv) * 100, "s-", color="#ff7f0e",
            label="Heston stochastic vol")
    ax.axhline(base_sigma * 100, color="#d62728", ls="--", label="flat BS vol (20%)")
    ax.axvline(S, color="grey", ls=":", alpha=0.7)
    ax.set_title("Implied-vol smiles generated by richer models")
    ax.set_xlabel("strike K")
    ax.set_ylabel("implied volatility (%)")
    ax.grid(alpha=0.3)
    ax.legend()
    return _finish(fig, save_path)


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
