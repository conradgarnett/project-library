"""
Portfolio of funding carries.

A single-coin carry is a thin, noisy stream. Running the carry across several
coins and combining them with a risk budget diversifies away idiosyncratic
basis/funding noise, which *raises* the risk-adjusted return (Sharpe) — a real,
honest improvement, not a modeling shortcut.

Built on the **basis-aware** per-coin returns (the honest ones), so the portfolio
Sharpe is comparable to the single-coin basis-aware numbers.

Weighting schemes
-----------------
equal        : 1/N in every coin.
inverse_vol  : weight ∝ 1 / trailing volatility (risk-balanced). Weights use a
               *trailing* window only (shifted one interval), so there is no
               look-ahead.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from ..common.metrics import max_drawdown, sharpe
from .carry import basis_carry_backtest
from .data import (
    FUNDING_INTERVALS_PER_YEAR,
    funding_history,
    perp_price_history,
    spot_price_history,
)


def carry_returns_panel(coins, limit: int = 1000, fee_bps: float = 5.0,
                        flip: bool = False) -> pd.DataFrame:
    """
    Basis-aware carry return streams for several coins, aligned on the common
    funding timestamps (one column per coin).
    """
    series = {}
    for c in coins:
        try:
            f = funding_history(c, limit=limit)
            perp = perp_price_history(c, limit=limit + 200)
            spot = spot_price_history(c, limit=limit + 200)
            series[c] = basis_carry_backtest(f, perp, spot, fee_bps=fee_bps,
                                             flip=flip).returns.rename(c)
        except Exception as e:  # noqa: BLE001 — a bad coin shouldn't sink the panel
            print(f"  [skip {c}] {type(e).__name__}: {e}")
    if not series:
        raise RuntimeError("no carry returns fetched")
    return pd.concat(series.values(), axis=1, join="inner").dropna()


def _weights(panel: pd.DataFrame, scheme: str, vol_window: int) -> pd.DataFrame:
    if scheme == "equal":
        w = pd.DataFrame(1.0, index=panel.index, columns=panel.columns)
    elif scheme == "inverse_vol":
        vol = panel.rolling(vol_window).std().shift(1)      # trailing only -> causal
        inv = 1.0 / vol.replace(0.0, np.nan)
        w = inv
    else:
        raise ValueError("scheme must be 'equal' or 'inverse_vol'")
    return w.div(w.sum(axis=1), axis=0)                      # normalize each row to 1


@dataclass
class PortfolioResult:
    returns: pd.Series
    weights: pd.DataFrame
    scheme: str
    ann_yield: float
    ann_return_compounded: float
    sharpe: float
    max_drawdown: float
    per_coin_sharpe: dict
    avg_standalone_sharpe: float
    diversification_ratio: float     # weighted-avg component vol / portfolio vol (>1 = benefit)
    n_intervals: int
    coins: list

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("returns"); d.pop("weights")
        return d

    def summary(self) -> str:
        lines = [
            f"Carry portfolio ({self.scheme}) over {len(self.coins)} coins, "
            f"{self.n_intervals} intervals",
            f"  annualized yield              : {self.ann_yield:6.2%}",
            f"  Sharpe (portfolio)            : {self.sharpe:6.2f}",
            f"  Sharpe (avg standalone coin)  : {self.avg_standalone_sharpe:6.2f}",
            f"  diversification ratio         : {self.diversification_ratio:6.2f}",
            f"  max drawdown                  : {self.max_drawdown:6.2%}",
            "  per-coin standalone Sharpe    : "
            + ", ".join(f"{c} {s:.1f}" for c, s in self.per_coin_sharpe.items()),
        ]
        return "\n".join(lines)


def carry_portfolio(panel: pd.DataFrame, scheme: str = "inverse_vol",
                    vol_window: int = 60) -> PortfolioResult:
    """
    Combine per-coin carry returns into a portfolio and quantify the
    diversification benefit vs the average standalone coin.
    """
    ppy = FUNDING_INTERVALS_PER_YEAR
    w = _weights(panel, scheme, vol_window)
    valid = w.notna().all(axis=1)
    panel_v, w = panel[valid], w[valid]

    port = (panel_v * w).sum(axis=1)
    per_coin = {c: sharpe(panel_v[c], ppy) for c in panel_v.columns}
    avg_standalone = float(np.mean(list(per_coin.values())))

    # Diversification ratio: weighted-average component vol / realized portfolio vol.
    comp_vol = panel_v.std()
    wavg_vol = float((w.mean() * comp_vol).sum())
    port_vol = float(port.std())
    div_ratio = wavg_vol / port_vol if port_vol > 0 else float("nan")

    n = len(port)
    return PortfolioResult(
        returns=port, weights=w, scheme=scheme,
        ann_yield=float(port.mean() * ppy),
        ann_return_compounded=float((1 + port).prod() ** (ppy / n) - 1) if n else 0.0,
        sharpe=sharpe(port, ppy),
        max_drawdown=max_drawdown(port)[0] if n else 0.0,
        per_coin_sharpe=per_coin,
        avg_standalone_sharpe=avg_standalone,
        diversification_ratio=div_ratio,
        n_intervals=n,
        coins=list(panel_v.columns),
    )
