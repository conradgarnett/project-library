"""
Options Mispricing feed — single-ticker, on-demand.

Reuses the CANONICAL scanner in ~/ai.algorithm (pricing.py + mispricing_scanner.py)
rather than duplicating the pricing logic here, so the terminal and the trading
brain stay in sync. Exposes analyze(ticker) → JSON for the OPT panel.
"""

from __future__ import annotations

import math
import os
import statistics
import sys
import time
from collections import defaultdict

# Pull in the canonical pricing/scanner from the trading-brain repo.
_AIALGO = os.path.expanduser("~/ai.algorithm")
if _AIALGO not in sys.path:
    sys.path.insert(0, _AIALGO)

try:
    import mispricing_scanner as _scan  # noqa: E402
    import pricing as _pricing  # noqa: E402
    import numpy as _np  # noqa: E402
    _AVAILABLE = True
    _IMPORT_ERR = ""
except Exception as e:  # pragma: no cover - import-time guard
    _AVAILABLE = False
    _IMPORT_ERR = str(e)

RISK_FREE = 0.04


def _err(ticker: str, msg: str) -> dict:
    return {"ticker": ticker, "error": msg, "spot": None, "rv": None,
            "n_contracts": 0, "n_flagged": 0, "rows": [], "flagged": [],
            "parity": [], "updated": time.time()}


def analyze(ticker: str, max_expiries: int = 6) -> dict:
    """Scan one ticker's option chains and rank contracts by smile mispricing."""
    ticker = (ticker or "").strip().upper()
    if not _AVAILABLE:
        return _err(ticker, f"scanner unavailable: {_IMPORT_ERR}")
    if not ticker or not _scan.valid_ticker(ticker):
        return _err(ticker, "invalid ticker")

    cfg = _scan.ScanConfig()
    cfg.max_expiries = max_expiries
    try:
        rows, parity = _scan.scan_ticker(ticker, cfg)
    except Exception as e:
        return _err(ticker, f"scan failed: {e}")

    # Per-expiry robust z-score of the smile residual (mirrors scanner.scan()).
    groups: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        if r.get("residual") is not None:
            groups[r["expiry"]].append(r["residual"])
    med, mad = {}, {}
    for exp, vals in groups.items():
        m = statistics.median(vals)
        med[exp] = m
        devs = [abs(v - m) for v in vals]
        mad[exp] = statistics.median(devs) * 1.4826 if devs else 0.0

    for r in rows:
        resid = r.get("residual")
        if resid is None:
            r["residual_z"], r["flagged"] = None, False
            continue
        s = mad[r["expiry"]]
        z = (resid - med[r["expiry"]]) / s if s > 0 else 0.0
        r["residual_z"] = round(z, 2)
        r["flagged"] = (abs(resid) >= cfg.residual_alert) or (abs(z) >= cfg.residual_z)

    rows.sort(key=lambda r: abs(r.get("residual") or 0), reverse=True)
    flagged = [r for r in rows if r.get("flagged")]
    spot = rows[0]["spot"] if rows else None
    rv = rows[0]["rv"] if rows else None

    return {
        "ticker": ticker,
        "spot": spot,
        "rv": rv,
        "n_contracts": len(rows),
        "n_flagged": len(flagged),
        "residual_alert": cfg.residual_alert,
        "residual_z": cfg.residual_z,
        "rows": rows[:120],
        "flagged": flagged[:40],
        "parity": parity,
        "updated": time.time(),
        "error": None if rows else "no liquid contracts (illiquid name or market closed)",
    }


def _mc_err(ticker: str, msg: str) -> dict:
    return {"ticker": ticker, "error": msg, "spot": None, "updated": time.time()}


def simulate(ticker: str, horizon_days: int = 30, vol_source: str = "iv",
             n_paths: int = 4000, n_steps: int = 60) -> dict:
    """
    Monte Carlo simulation of the underlying's price paths to a horizon, plus
    the MC-vs-Black-Scholes value of the ATM option over that window.

    vol_source: "iv" → use ATM implied vol from the nearest expiry (falls back
    to realized if no chain); "rv" → use realized volatility.
    Returns sample paths + percentile bands + terminal distribution for plotting.
    """
    ticker = (ticker or "").strip().upper()
    if not _AVAILABLE:
        return _mc_err(ticker, f"engine unavailable: {_IMPORT_ERR}")
    if not ticker or not _scan.valid_ticker(ticker):
        return _mc_err(ticker, "invalid ticker")
    horizon_days = max(2, min(int(horizon_days or 30), 365))
    r = RISK_FREE

    # Pull spot, realized vol, and (if available) ATM IV near the horizon by
    # reusing the scanner — same data path as the mispricing table.
    spot = rv = atm_iv = None
    expiry_used = None
    try:
        cfg = _scan.ScanConfig()
        cfg.max_expiries = 6
        rows, _ = _scan.scan_ticker(ticker, cfg)
    except Exception:
        rows = []
    if rows:
        spot, rv = rows[0]["spot"], rows[0]["rv"]
        best = min(rows, key=lambda x: abs(x["dte"] - horizon_days))
        atm_iv, expiry_used = best["atm_iv"], best["expiry"]

    # Fallback: no liquid chain → get spot + realized vol straight from history.
    if spot is None:
        try:
            import yfinance as yf  # provided by the bloomberg env
            hist = yf.Ticker(ticker).history(period="6mo")
            if hist.empty:
                return _mc_err(ticker, "no price data")
            spot = float(hist["Close"].iloc[-1])
            rv = _scan.realized_vol(hist["Close"], 30)
        except Exception as e:
            return _mc_err(ticker, f"data fetch failed: {e}")

    if not rv or not math.isfinite(rv):
        return _mc_err(ticker, "could not estimate volatility")

    use_iv = vol_source == "iv" and atm_iv and math.isfinite(atm_iv)
    sigma = float(atm_iv) if use_iv else float(rv)
    T = horizon_days / 365.25
    K = round(spot)  # ATM strike for the priced option

    times, paths = _pricing.simulate_paths(spot, T, r, sigma, q=0.0,
                                           n_paths=n_paths, n_steps=n_steps, seed=42)
    terminal = paths[:, -1]

    # Percentile envelope across all paths at each step (the fan).
    pct = lambda p: [round(float(v), 4) for v in _np.percentile(paths, p, axis=0)]
    bands = {"p5": pct(5), "p25": pct(25), "p50": pct(50), "p75": pct(75), "p95": pct(95)}

    # A thin set of sample paths for visual texture.
    n_sample = min(28, n_paths)
    idx = _np.linspace(0, n_paths - 1, n_sample).astype(int)
    sample = [[round(float(v), 4) for v in paths[i]] for i in idx]

    # Terminal-price histogram.
    counts, edges = _np.histogram(terminal, bins=40)
    centers = (edges[:-1] + edges[1:]) / 2

    # Option value: MC vs closed-form, plus probability ITM (call).
    bs = _pricing.bs_price(spot, K, T, r, sigma, "C")
    mc = _pricing.mc_price(spot, K, T, r, sigma, "C", n_paths=max(n_paths, 20000), seed=7)
    prob_itm = float((terminal > K).mean())

    return {
        "ticker": ticker,
        "spot": round(float(spot), 2),
        "rv": round(float(rv), 4),
        "atm_iv": round(float(atm_iv), 4) if atm_iv else None,
        "sigma": round(sigma, 4),
        "vol_source": "iv" if use_iv else "rv",
        "horizon_days": horizon_days,
        "expiry_used": expiry_used,
        "n_paths": n_paths,
        "times_days": [round(float(t) * 365.25, 2) for t in times],
        "bands": bands,
        "sample_paths": sample,
        "terminal": {
            "x": [round(float(c), 2) for c in centers],
            "y": [int(c) for c in counts],
            "p5": round(float(_np.percentile(terminal, 5)), 2),
            "p50": round(float(_np.percentile(terminal, 50)), 2),
            "p95": round(float(_np.percentile(terminal, 95)), 2),
            "mean": round(float(terminal.mean()), 2),
        },
        "option": {
            "strike": K, "kind": "C", "T_days": horizon_days,
            "bs_price": round(bs, 3),
            "mc_price": round(mc["price"], 3),
            "mc_ci95": round(mc["ci95"], 3),
            "prob_itm": round(prob_itm, 3),
        },
        "updated": time.time(),
        "error": None,
    }
