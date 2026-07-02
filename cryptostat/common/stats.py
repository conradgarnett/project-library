"""
Cointegration / mean-reversion statistics — pure numpy + scipy (no statsmodels).

The building blocks a pairs-trading strategy needs:

  adf_test        Augmented Dickey-Fuller unit-root test (is a series stationary?)
  engle_granger   two-step cointegration test (do two prices share a stationary
                  linear combination — i.e. a tradeable spread?)
  hedge_ratio     the ratio to combine the two legs (OLS or total-least-squares)
  half_life       Ornstein-Uhlenbeck mean-reversion speed of a spread
  zscore          standardized spread, the raw material of the trading signal

Critical values are MacKinnon's standard large-sample values; the reported
p-value is a documented interpolation (see ``_approx_pvalue``) and is meant for
ranking pairs, not for publication-grade inference.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# MacKinnon asymptotic critical values.
_ADF_CRIT = {
    "n":  {0.01: -2.5658, 0.05: -1.9411, 0.10: -1.6168},
    "c":  {0.01: -3.4336, 0.05: -2.8621, 0.10: -2.5671},
    "ct": {0.01: -3.9638, 0.05: -3.4126, 0.10: -3.1279},
}
# Engle-Granger residual-based cointegration crit values, 2 series, constant.
_EG_CRIT = {0.01: -3.9001, 0.05: -3.3377, 0.10: -3.0462}


def _ols(X: np.ndarray, y: np.ndarray):
    """Ordinary least squares. Returns (beta, resid, se_beta)."""
    beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    n, k = X.shape
    dof = max(n - k, 1)
    sigma2 = resid @ resid / dof
    xtx_inv = np.linalg.inv(X.T @ X)
    se = np.sqrt(np.diag(sigma2 * xtx_inv))
    return beta, resid, se


def _approx_pvalue(stat: float, crit: dict) -> float:
    """
    Coarse p-value by interpolating the test statistic against the 1/5/10%
    critical values (log-linear), clamped into (0, 1). Approximate — use for
    ranking, not for exact inference.
    """
    xs = [crit[0.01], crit[0.05], crit[0.10], 0.0]
    ys = [0.01, 0.05, 0.10, 0.5]
    # More negative stat => smaller p-value.
    if stat <= xs[0]:
        return max(0.001, 0.01 * np.exp((stat - xs[0])))
    if stat >= xs[-1]:
        return min(0.999, 0.5 + 0.5 * (1 - np.exp(-(stat))))
    return float(np.interp(stat, xs, ys))


@dataclass
class ADFResult:
    stat: float
    pvalue: float
    lags: int
    nobs: int
    crit: dict
    regression: str

    def is_stationary(self, alpha: float = 0.05) -> bool:
        return self.stat < self.crit[alpha]


def adf_test(y, lags="auto", regression: str = "c", max_lags: int | None = None) -> ADFResult:
    """
    Augmented Dickey-Fuller test.  H0: the series has a unit root (is a random
    walk, non-stationary).  Rejecting H0 (stat below the critical value) implies
    the series is mean-reverting.

    regression : "c" constant (default), "ct" constant+trend, "n" none.
    lags       : number of lagged differences, or "auto" (Schwert rule).
    """
    y = np.asarray(y, dtype=float)
    y = y[~np.isnan(y)]
    n = y.size
    if regression not in _ADF_CRIT:
        raise ValueError("regression must be 'c', 'ct', or 'n'")

    if lags == "auto":
        cap = max_lags if max_lags is not None else int(np.ceil(12 * (n / 100.0) ** 0.25))
        lags = int(min(cap, max(0, n // 2 - 2)))

    dy = np.diff(y)
    # Build the regression:  dy_t = gamma*y_{t-1} + sum psi_i dy_{t-i} + det.
    y_lag = y[:-1]
    rows = n - 1 - lags
    if rows <= len(_ADF_CRIT[regression]) + lags + 2:
        raise ValueError("series too short for the requested number of lags")

    cols = [y_lag[lags:]]
    for i in range(1, lags + 1):
        cols.append(dy[lags - i: -i])
    X = np.column_stack(cols)
    if regression in ("c", "ct"):
        X = np.column_stack([X, np.ones(rows)])
    if regression == "ct":
        X = np.column_stack([X, np.arange(rows, dtype=float)])
    target = dy[lags:]

    beta, _, se = _ols(X, target)
    stat = beta[0] / se[0]                       # t-stat on gamma
    crit = _ADF_CRIT[regression]
    return ADFResult(stat=float(stat), pvalue=_approx_pvalue(stat, crit),
                     lags=lags, nobs=rows, crit=crit, regression=regression)


def hedge_ratio(y, x, method: str = "ols") -> float:
    """
    Hedge ratio β for the spread ``y - β·x``.

    method="ols" : slope of OLS y ~ const + x (asymmetric in y, x).
    method="tls" : total least squares / orthogonal regression (symmetric),
        via the first principal component of the demeaned (x, y) cloud.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if method == "ols":
        X = np.column_stack([np.ones_like(x), x])
        beta, _, _ = _ols(X, y)
        return float(beta[1])
    if method == "tls":
        M = np.column_stack([x - x.mean(), y - y.mean()])
        _, _, Vt = np.linalg.svd(M, full_matrices=False)
        vx, vy = Vt[0]
        return float(vy / vx)
    raise ValueError("method must be 'ols' or 'tls'")


def half_life(spread) -> float:
    """
    Mean-reversion half-life (in observations) from an Ornstein-Uhlenbeck /
    AR(1) fit:  Δs_t = a + b·s_{t-1} + ε  →  half-life = -ln(2)/b.
    Returns np.inf if the series is not mean-reverting (b >= 0).
    """
    s = np.asarray(spread, dtype=float)
    s = s[~np.isnan(s)]
    lag = s[:-1]
    delta = np.diff(s)
    X = np.column_stack([np.ones_like(lag), lag])
    beta, _, _ = _ols(X, delta)
    b = beta[1]
    if b >= 0:
        return np.inf
    return float(-np.log(2) / b)


def zscore(series, window: int | None = None):
    """
    Standardized series. ``window=None`` uses the full-sample mean/std;
    an integer uses a trailing rolling window (returns a numpy array aligned to
    the input, with leading NaNs).
    """
    s = np.asarray(series, dtype=float)
    if window is None:
        return (s - np.nanmean(s)) / np.nanstd(s)
    out = np.full_like(s, np.nan)
    for t in range(window - 1, s.size):
        w = s[t - window + 1: t + 1]
        mu, sd = w.mean(), w.std()
        out[t] = (s[t] - mu) / sd if sd > 0 else 0.0
    return out


@dataclass
class CointResult:
    stat: float
    pvalue: float
    alpha: float
    beta: float                # hedge ratio (slope)
    intercept: float
    resid: np.ndarray          # the spread
    half_life: float
    crit: dict

    def is_cointegrated(self, alpha: float = 0.05) -> bool:
        return self.stat < self.crit[alpha]


def engle_granger(y, x, alpha: float = 0.05, adf_lags="auto") -> CointResult:
    """
    Engle-Granger two-step cointegration test.

    Step 1: regress y on x (with a constant) → residual spread.
    Step 2: ADF (no-constant) on the spread. If the spread is stationary the two
    series are cointegrated and their spread is tradeable.

    Uses Engle-Granger-specific critical values (stricter than a plain ADF
    because the spread was fitted, not observed).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    X = np.column_stack([np.ones_like(x), x])
    beta, resid, _ = _ols(X, y)
    adf = adf_test(resid, lags=adf_lags, regression="n")
    return CointResult(
        stat=adf.stat, pvalue=_approx_pvalue(adf.stat, _EG_CRIT), alpha=alpha,
        beta=float(beta[1]), intercept=float(beta[0]), resid=resid,
        half_life=half_life(resid), crit=_EG_CRIT,
    )
