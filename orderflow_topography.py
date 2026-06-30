#!/usr/bin/env python3
"""
Order-Flow 3D Topography
========================

Renders the options order-flow "landscape" as a 3D terrain surface:

    X axis : strike (price level)
    Y axis : days to expiry (DTE), across multiple expiries
    Z axis : flow intensity  (selectable):
               gex      -> dealer Gamma Exposure per strike (default)
               volume   -> call+put contract volume
               netflow  -> call volume - put volume (directional pressure)
               oi       -> call+put open interest

Markers:
    * the spot price (vertical plane through the terrain)
    * the gamma-flip ridge (Z = 0 crossing) when metric == gex
    * the call wall / put wall (largest call-OI / put-OI strikes)

Data:
    Live option chains via yfinance (no API key). If yfinance is unavailable or
    the fetch fails, a realistic SYNTHETIC chain is generated so the plot always
    renders.

Usage:
    python orderflow_topography.py --ticker SPY --metric gex --expiries 6
    python orderflow_topography.py --ticker NVDA --metric netflow
    python orderflow_topography.py                 # synthetic SPY-like demo

Output:
    Saves a PNG (always) and, if plotly is installed, an interactive HTML.

Connects to the vault research: [[Gamma Exposure]], [[Options Flow]],
[[Order Flow]].
"""

from __future__ import annotations

import argparse
import math
import os
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional

import numpy as np

import matplotlib
matplotlib.use("Agg")                       # headless: save to file, no display
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D      # noqa: F401  (registers 3d proj)

try:
    import yfinance as yf
    _HAVE_YF = True
except Exception:
    _HAVE_YF = False

CONTRACT_MULTIPLIER = 100
SQRT_2PI = math.sqrt(2.0 * math.pi)


# --------------------------------------------------------------------------- #
# Option math
# --------------------------------------------------------------------------- #

def norm_pdf(x: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * np.asarray(x, dtype=float) ** 2) / SQRT_2PI


def bs_gamma(S: float, K: np.ndarray, T: float, r: float, sigma: np.ndarray) -> np.ndarray:
    """Black-Scholes gamma per $1 move (vectorized over strikes)."""
    K = np.asarray(K, dtype=float)
    sigma = np.maximum(np.asarray(sigma, dtype=float), 1e-6)
    T = max(T, 1e-6)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    return norm_pdf(d1) / (S * sigma * math.sqrt(T))


# --------------------------------------------------------------------------- #
# Data containers
# --------------------------------------------------------------------------- #

@dataclass
class ExpirySlice:
    """One expiry's per-strike flow data."""
    dte: int
    strikes: np.ndarray
    call_vol: np.ndarray
    put_vol: np.ndarray
    call_oi: np.ndarray
    put_oi: np.ndarray
    call_iv: np.ndarray
    put_iv: np.ndarray


@dataclass
class FlowBook:
    ticker: str
    spot: float
    slices: List[ExpirySlice]


# --------------------------------------------------------------------------- #
# Data acquisition
# --------------------------------------------------------------------------- #

def fetch_flow_yfinance(ticker: str, n_expiries: int) -> Optional[FlowBook]:
    if not _HAVE_YF:
        return None
    try:
        tk = yf.Ticker(ticker)
        spot = float(tk.fast_info.get("last_price")
                     or tk.history(period="1d")["Close"].iloc[-1])
        exps = tk.options[:n_expiries]
        if not exps:
            return None
        today = date.today()
        slices: List[ExpirySlice] = []
        for exp in exps:
            oc = tk.option_chain(exp)
            calls, puts = oc.calls, oc.puts
            strikes = np.union1d(calls["strike"].values, puts["strike"].values).astype(float)

            def col(df, name):
                m = {float(k): float(v) for k, v in zip(df["strike"], df[name])
                     if v == v}
                return np.array([m.get(float(k), 0.0) for k in strikes])

            dte = max((date.fromisoformat(exp) - today).days, 1)
            slices.append(ExpirySlice(
                dte=dte, strikes=strikes,
                call_vol=col(calls, "volume"), put_vol=col(puts, "volume"),
                call_oi=col(calls, "openInterest"), put_oi=col(puts, "openInterest"),
                call_iv=col(calls, "impliedVolatility"),
                put_iv=col(puts, "impliedVolatility"),
            ))
        return FlowBook(ticker=ticker, spot=spot, slices=slices)
    except Exception as exc:
        print(f"[warn] yfinance fetch failed ({exc}); using synthetic data.")
        return None


def synthetic_flow(ticker: str, spot: float, n_expiries: int,
                   seed: int = 7) -> FlowBook:
    """Realistic synthetic flow: smile IV, ATM-peaked volume, OI walls at rounds."""
    rng = np.random.default_rng(seed)
    slices: List[ExpirySlice] = []
    for i in range(n_expiries):
        dte = int(7 * (i + 1) + rng.integers(0, 4))
        T = dte / 365.0
        strikes = np.round(np.linspace(spot * 0.7, spot * 1.3, 41) / 1.0) * 1.0
        strikes = np.unique(strikes)
        k = np.log(strikes / spot)
        # smile: higher IV in wings, term decay
        iv = (0.18 + 0.6 * k ** 2 - 0.25 * k) / math.sqrt(max(T, 0.02))
        iv = np.clip(iv, 0.08, 2.5)
        # volume peaks ATM, decays in wings, more in near expiries
        atm_peak = np.exp(-(k ** 2) / (2 * 0.05)) * (1.0 / (1 + i))
        call_vol = (atm_peak * rng.uniform(3000, 9000)
                    + rng.uniform(0, 400, strikes.size))
        put_vol = (atm_peak * rng.uniform(3000, 9000)
                   + rng.uniform(0, 400, strikes.size))
        # OI walls at round numbers (multiples of 5% of spot)
        wall_mask = (np.abs(strikes % (round(spot * 0.05) or 1)) < 1e-6)
        call_oi = atm_peak * rng.uniform(5000, 15000) + wall_mask * rng.uniform(0, 20000)
        put_oi = atm_peak * rng.uniform(5000, 15000) + wall_mask * rng.uniform(0, 20000)
        # extra put OI below spot (hedging demand)
        put_oi += (strikes < spot) * rng.uniform(0, 8000, strikes.size)
        slices.append(ExpirySlice(
            dte=dte, strikes=strikes,
            call_vol=call_vol, put_vol=put_vol,
            call_oi=call_oi, put_oi=put_oi,
            call_iv=iv.copy(), put_iv=iv.copy(),
        ))
    return FlowBook(ticker=ticker, spot=spot, slices=slices)


# --------------------------------------------------------------------------- #
# Metric computation
# --------------------------------------------------------------------------- #

def slice_metric(sl: ExpirySlice, spot: float, metric: str, r: float) -> np.ndarray:
    """Compute the chosen Z metric per strike for one expiry slice."""
    T = sl.dte / 365.0
    if metric == "gex":
        cg = bs_gamma(spot, sl.strikes, T, r, np.where(sl.call_iv > 0, sl.call_iv, 0.3))
        pg = bs_gamma(spot, sl.strikes, T, r, np.where(sl.put_iv > 0, sl.put_iv, 0.3))
        # SqueezeMetrics-style: long call gamma, short put gamma (sign convention
        # documented; flip with --flip-sign if your convention differs).
        gex = (cg * sl.call_oi - pg * sl.put_oi) * CONTRACT_MULTIPLIER * spot ** 2 * 0.01
        return gex / 1e6                      # $mm of gamma per 1% move
    if metric == "volume":
        return sl.call_vol + sl.put_vol
    if metric == "netflow":
        return sl.call_vol - sl.put_vol
    if metric == "oi":
        return sl.call_oi + sl.put_oi
    raise ValueError(f"unknown metric: {metric}")


def build_grid(book: FlowBook, metric: str, r: float, n_strikes: int = 80,
               lo: float = 0.7, hi: float = 1.3):
    """Interpolate every expiry's metric onto a common strike grid -> mesh."""
    spot = book.spot
    common = np.linspace(spot * lo, spot * hi, n_strikes)
    dtes = sorted({s.dte for s in book.slices})
    # one row per unique DTE (average if duplicates)
    Z = np.zeros((len(dtes), n_strikes))
    for sl in sorted(book.slices, key=lambda s: s.dte):
        vals = slice_metric(sl, spot, metric, r)
        order = np.argsort(sl.strikes)
        interp = np.interp(common, sl.strikes[order], vals[order], left=0.0, right=0.0)
        row = dtes.index(sl.dte)
        Z[row] = interp
    X, Y = np.meshgrid(common, np.array(dtes, dtype=float))
    return X, Y, Z, common, np.array(dtes)


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def _wall_strikes(book: FlowBook):
    """Aggregate call/put OI across expiries; return (call_wall, put_wall)."""
    agg = {}
    for sl in book.slices:
        for K, co, po in zip(sl.strikes, sl.call_oi, sl.put_oi):
            c, p = agg.get(K, (0.0, 0.0))
            agg[K] = (c + co, p + po)
    if not agg:
        return None, None
    call_wall = max(agg.items(), key=lambda kv: kv[1][0])[0]
    put_wall = max(agg.items(), key=lambda kv: kv[1][1])[0]
    return call_wall, put_wall


def render(book: FlowBook, metric: str, r: float, out_png: str,
           make_html: bool = True) -> str:
    X, Y, Z, strikes, dtes = build_grid(book, metric, r)
    spot = book.spot

    cmap = {"gex": cm.terrain, "volume": cm.viridis,
            "netflow": cm.RdBu_r, "oi": cm.magma}.get(metric, cm.terrain)

    fig = plt.figure(figsize=(13, 8))
    ax = fig.add_subplot(111, projection="3d")
    surf = ax.plot_surface(X, Y, Z, cmap=cmap, linewidth=0, antialiased=True,
                           rcount=80, ccount=80, alpha=0.95)

    # spot plane (vertical sheet at x = spot)
    zmin, zmax = float(np.min(Z)), float(np.max(Z))
    yspan = np.array([dtes.min(), dtes.max()])
    zspan = np.array([zmin, zmax])
    YY, ZZ = np.meshgrid(yspan, zspan)
    XX = np.full_like(YY, spot)
    ax.plot_surface(XX, YY, ZZ, color="cyan", alpha=0.18)
    ax.text(spot, dtes.max(), zmax, "  spot", color="cyan", fontsize=9)

    # gamma-flip ridge (Z = 0) for GEX
    if metric == "gex":
        try:
            ax.contour(X, Y, Z, levels=[0.0], colors="red", linewidths=2.0,
                       offset=zmin)
            ax.text2D(0.02, 0.92, "red line = gamma flip (GEX=0)",
                      transform=ax.transAxes, color="red", fontsize=9)
        except Exception:
            pass

    # call / put walls
    cw, pw = _wall_strikes(book)
    if cw is not None and strikes.min() <= cw <= strikes.max():
        ax.plot([cw, cw], [dtes.min(), dtes.max()], [zmin, zmin],
                color="green", lw=2)
        ax.text(cw, dtes.min(), zmin, " call wall", color="green", fontsize=8)
    if pw is not None and strikes.min() <= pw <= strikes.max():
        ax.plot([pw, pw], [dtes.min(), dtes.max()], [zmin, zmin],
                color="orange", lw=2)
        ax.text(pw, dtes.min(), zmin, " put wall", color="orange", fontsize=8)

    zlabel = {"gex": "Dealer GEX ($mm / 1% move)",
              "volume": "Contract volume",
              "netflow": "Net flow (call - put vol)",
              "oi": "Open interest"}[metric]
    ax.set_xlabel("Strike")
    ax.set_ylabel("Days to expiry")
    ax.set_zlabel(zlabel)
    ax.set_title(f"{book.ticker}  —  Order-Flow 3D Topography  [{metric}]   "
                 f"spot={spot:.2f}", fontsize=13)
    ax.view_init(elev=32, azim=-58)
    fig.colorbar(surf, shrink=0.5, aspect=12, pad=0.08, label=zlabel)
    fig.tight_layout()
    fig.savefig(out_png, dpi=140)
    plt.close(fig)
    print(f"[ok] saved {out_png}")

    if make_html:
        _try_plotly(X, Y, Z, book, metric, zlabel, out_png.replace(".png", ".html"))
    return out_png


def _try_plotly(X, Y, Z, book, metric, zlabel, out_html):
    try:
        import plotly.graph_objects as go
    except Exception:
        return
    fig = go.Figure(data=[go.Surface(
        x=X, y=Y, z=Z,
        colorscale="Earth" if metric == "gex" else "Viridis",
        colorbar=dict(title=zlabel))])
    fig.update_layout(
        title=f"{book.ticker} — Order-Flow 3D Topography [{metric}] spot={book.spot:.2f}",
        scene=dict(xaxis_title="Strike", yaxis_title="Days to expiry",
                   zaxis_title=zlabel),
        width=1100, height=750)
    fig.write_html(out_html)
    print(f"[ok] saved interactive {out_html}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Order-Flow 3D Topography")
    ap.add_argument("--ticker", default="SPY")
    ap.add_argument("--metric", default="gex",
                    choices=["gex", "volume", "netflow", "oi"])
    ap.add_argument("--expiries", type=int, default=6)
    ap.add_argument("--rate", type=float, default=0.05)
    ap.add_argument("--spot", type=float, default=None,
                    help="spot for synthetic mode (default 500 SPY-like)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--no-html", action="store_true")
    args = ap.parse_args(argv)

    book = fetch_flow_yfinance(args.ticker, args.expiries)
    if book is None:
        spot = args.spot or 500.0
        print(f"[info] using synthetic flow for {args.ticker} (spot {spot}).")
        book = synthetic_flow(args.ticker, spot, args.expiries)

    out = args.out or f"orderflow_{args.ticker}_{args.metric}.png"
    render(book, args.metric, args.rate, out, make_html=not args.no_html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
