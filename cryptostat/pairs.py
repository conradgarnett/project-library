"""
Pair screening: scan a price panel for cointegrated, tradeable pairs.

Every unordered pair is tested with Engle-Granger; results are ranked so the
most promising candidates (stationary spread, sensible half-life) surface first.
A correlation prefilter avoids wasting cointegration tests on unrelated series.

    from cryptostat.data import price_panel
    from cryptostat.pairs import screen_pairs
    panel = price_panel(["BTC-USD","ETH-USD","LTC-USD","BCH-USD"], days=730)
    table = screen_pairs(panel)          # ranked DataFrame
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

from .stats import engle_granger


def screen_pairs(
    panel: pd.DataFrame, alpha: float = 0.05,
    min_corr: float = 0.5, min_half_life: float = 1.0, max_half_life: float = 252.0,
    use_log: bool = True,
) -> pd.DataFrame:
    """
    Test every pair of columns for cointegration and return a ranked table.

    Parameters
    ----------
    alpha : significance level for the cointegration flag.
    min_corr : skip pairs whose price correlation is below this (prefilter).
    min/max_half_life : keep only pairs whose mean-reversion half-life is in a
        tradeable range (too fast = noise/cost; too slow = capital tied up).
    use_log : test log-prices (usually more stable for cointegration).

    Ranking: cointegrated pairs first, then by ascending Engle-Granger stat
    (more negative = stronger evidence of a stationary spread).
    """
    df = np.log(panel) if use_log else panel
    cols = list(df.columns)
    rows = []
    for a, b in combinations(cols, 2):
        sa, sb = df[a], df[b]
        mask = sa.notna() & sb.notna()
        if mask.sum() < 60:
            continue
        x, y = sa[mask].values, sb[mask].values
        corr = float(np.corrcoef(x, y)[0, 1])
        if abs(corr) < min_corr:
            continue
        # Test both directions; keep the stronger (regression is asymmetric).
        r1 = engle_granger(y, x)
        r2 = engle_granger(x, y)
        res, (dep, ind) = (r1, (b, a)) if r1.stat <= r2.stat else (r2, (a, b))
        hl = res.half_life
        rows.append({
            "dependent": dep, "independent": ind, "corr": corr,
            "eg_stat": res.stat, "eg_pvalue": res.pvalue,
            "beta": res.beta, "half_life": hl,
            "cointegrated": res.is_cointegrated(alpha),
            "tradeable_hl": (min_half_life <= hl <= max_half_life),
        })

    if not rows:
        return pd.DataFrame(columns=["dependent", "independent", "corr", "eg_stat",
                                     "eg_pvalue", "beta", "half_life",
                                     "cointegrated", "tradeable_hl"])
    table = pd.DataFrame(rows)
    table["candidate"] = table["cointegrated"] & table["tradeable_hl"]
    return table.sort_values(
        ["candidate", "eg_stat"], ascending=[False, True]
    ).reset_index(drop=True)
