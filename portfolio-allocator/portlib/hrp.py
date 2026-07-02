"""
Hierarchical Risk Parity (HRP) — López de Prado (2016).

HRP avoids inverting the (noisy) covariance matrix entirely. It (1) clusters
assets by correlation, (2) reorders the covariance so similar assets sit
together (quasi-diagonalization), then (3) splits capital top-down by
inverse-variance down the cluster tree (recursive bisection). It is robust to
estimation error and tends to produce well-diversified, stable weights.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, to_tree
from scipy.spatial.distance import squareform

from .covariance import correlation_from_cov


def _quasi_diag(link):
    """Return the leaf order induced by the linkage tree."""
    tree = to_tree(link, rd=False)
    return tree.pre_order()          # list of original leaf indices


def _inverse_variance_weights(cov_slice):
    ivp = 1.0 / np.diag(cov_slice)
    return ivp / ivp.sum()


def _cluster_var(cov, idx):
    sub = cov[np.ix_(idx, idx)]
    w = _inverse_variance_weights(sub)
    return float(w @ sub @ w)


def hrp_weights(cov):
    """
    Hierarchical Risk Parity weights from a covariance matrix (DataFrame or array).
    """
    is_df = isinstance(cov, pd.DataFrame)
    labels = list(cov.index) if is_df else None
    S = np.asarray(cov, dtype=float)
    n = S.shape[0]
    if n == 1:
        w = np.array([1.0])
        return pd.Series(w, index=labels) if is_df else w

    corr = np.asarray(correlation_from_cov(S))
    dist = np.sqrt(np.clip((1.0 - corr) / 2.0, 0.0, None))   # correlation distance
    link = linkage(squareform(dist, checks=False), method="single")
    order = _quasi_diag(link)

    # Recursive bisection.
    w = np.ones(n)
    clusters = [order]
    while clusters:
        new = []
        for cl in clusters:
            if len(cl) <= 1:
                continue
            half = len(cl) // 2
            left, right = cl[:half], cl[half:]
            var_l, var_r = _cluster_var(S, left), _cluster_var(S, right)
            alpha = 1.0 - var_l / (var_l + var_r)   # inverse-variance split
            for i in left:
                w[i] *= alpha
            for i in right:
                w[i] *= (1.0 - alpha)
            new += [left, right]
        clusters = new

    w = w / w.sum()
    return pd.Series(w, index=labels) if is_df else w
