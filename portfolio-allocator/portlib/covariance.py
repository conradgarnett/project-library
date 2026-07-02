"""
Covariance estimation for portfolio construction.

The sample covariance is noisy and often ill-conditioned when the number of
assets is not small relative to the sample length — which wrecks mean-variance
optimizers (they load up on estimation error). **Ledoit-Wolf shrinkage** pulls
the sample matrix toward a well-conditioned target (here a scaled identity),
with an analytically-optimal shrinkage intensity. This is the standard fix and
what makes the optimizers below behave.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _as_matrix(returns):
    if isinstance(returns, pd.DataFrame):
        return returns.values, list(returns.columns)
    return np.asarray(returns, dtype=float), None


def sample_covariance(returns) -> pd.DataFrame | np.ndarray:
    """Plain sample covariance matrix of a (T × N) returns panel."""
    X, cols = _as_matrix(returns)
    S = np.cov(X, rowvar=False, ddof=1)
    return pd.DataFrame(S, index=cols, columns=cols) if cols else S


def ledoit_wolf(returns):
    """
    Ledoit-Wolf (2004) shrinkage toward a scaled-identity target.

        Σ = δ·(μ·I) + (1−δ)·S

    with S the sample covariance, μ the average variance, and δ the closed-form
    optimal shrinkage intensity in [0, 1]. Returns (Σ, δ).
    """
    X, cols = _as_matrix(returns)
    T, N = X.shape
    Xc = X - X.mean(axis=0)
    S = (Xc.T @ Xc) / T
    mu = np.trace(S) / N
    F = mu * np.eye(N)

    d2 = np.sum((S - F) ** 2)                       # ||S - F||_F^2
    # b̄² = (1/T²)·Σ_t ||x_t x_tᵀ − S||_F²  (vectorized identity)
    row_sq = np.sum(Xc ** 2, axis=1)               # ||x_t||² per obs
    b2 = (np.sum(row_sq ** 2) / T ** 2) - np.sum(S ** 2) / T
    b2 = max(0.0, min(b2, d2))
    delta = b2 / d2 if d2 > 0 else 0.0

    Sigma = delta * F + (1.0 - delta) * S
    if cols:
        Sigma = pd.DataFrame(Sigma, index=cols, columns=cols)
    return Sigma, float(delta)


def cov_estimate(returns, method: str = "ledoit"):
    """Convenience: 'sample' or 'ledoit' (default) covariance as a DataFrame/array."""
    if method == "sample":
        return sample_covariance(returns)
    if method == "ledoit":
        return ledoit_wolf(returns)[0]
    raise ValueError("method must be 'sample' or 'ledoit'")


def correlation_from_cov(cov):
    """Correlation matrix from a covariance matrix (preserves labels)."""
    C = np.asarray(cov, dtype=float)
    d = np.sqrt(np.diag(C))
    corr = C / np.outer(d, d)
    np.fill_diagonal(corr, 1.0)
    if isinstance(cov, pd.DataFrame):
        return pd.DataFrame(corr, index=cov.index, columns=cov.columns)
    return corr
