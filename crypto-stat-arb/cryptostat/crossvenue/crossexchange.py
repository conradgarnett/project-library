"""
Cross-exchange arbitrage: hunt for price dislocations of the *same* asset across
venues.

Two lenses:

  live_arbitrage()        A snapshot of current bid/ask across venues. For every
                          ordered (buy-here, sell-there) route it computes the
                          gross edge and the edge NET of both venues' taker fees.
                          Positive net edge = an executable spot arbitrage.

  cross_exchange_spread() The historical daily dislocation (dearest vs cheapest
                          venue) over time, so you can see how often and how far
                          prices diverge — and how often that beats trading costs.

Honesty note: between major USD venues, gross dislocations (single-digit to low
tens of bps) are usually smaller than round-trip taker fees (~50-100 bps), so
net edges are typically negative — markets are efficient. Real edges tend to
appear only in brief volatility spikes, on thinner altcoins, or via funding/
basis rather than spot. Measuring that is exactly the point.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations

import numpy as np
import pandas as pd

from .exchanges import TAKER_FEE_BPS, USD_EXCHANGES, daily_close_panel, live_quote_panel


@dataclass
class ArbOpportunity:
    asset: str
    buy_on: str
    sell_on: str
    buy_ask: float
    sell_bid: float
    gross_bps: float
    fee_bps: float
    net_bps: float


def live_arbitrage(asset: str, exchanges=None, use_fees: bool = True, quotes=None):
    """
    Snapshot cross-exchange arbitrage for one asset.

    Returns (best_opportunity, table) where ``table`` has every ordered venue
    route ranked by net edge (bps). Buy at a venue's ask, sell at another's bid;
    net edge subtracts both venues' taker fees.
    """
    q = quotes if quotes is not None else live_quote_panel(asset, exchanges)
    rows = []
    for buy, sell in permutations(q.index, 2):
        ask = q.loc[buy, "ask"]
        bid = q.loc[sell, "bid"]
        gross = (bid - ask) / ask * 1e4
        fee = (TAKER_FEE_BPS.get(buy, 0) + TAKER_FEE_BPS.get(sell, 0)) if use_fees else 0.0
        rows.append({
            "buy_on": buy, "sell_on": sell, "buy_ask": ask, "sell_bid": bid,
            "gross_bps": gross, "fee_bps": fee, "net_bps": gross - fee,
        })
    table = pd.DataFrame(rows).sort_values("net_bps", ascending=False).reset_index(drop=True)
    top = table.iloc[0]
    best = ArbOpportunity(asset, top["buy_on"], top["sell_on"], top["buy_ask"],
                          top["sell_bid"], top["gross_bps"], top["fee_bps"], top["net_bps"])
    return best, table


def scan_live_arbitrage(assets, exchanges=None, use_fees: bool = True) -> pd.DataFrame:
    """Run :func:`live_arbitrage` across many assets; one best-route row each,
    ranked by net edge — the fastest way to spot where an opportunity exists."""
    rows = []
    for a in assets:
        try:
            best, _ = live_arbitrage(a, exchanges, use_fees)
            rows.append({
                "asset": a, "buy_on": best.buy_on, "sell_on": best.sell_on,
                "gross_bps": best.gross_bps, "fee_bps": best.fee_bps,
                "net_bps": best.net_bps, "executable": best.net_bps > 0,
            })
        except Exception as e:  # noqa: BLE001
            print(f"  [skip {a}] {type(e).__name__}: {e}")
    return pd.DataFrame(rows).sort_values("net_bps", ascending=False).reset_index(drop=True)


def cross_exchange_spread(asset: str, exchanges=None, days: int = 365, panel=None) -> pd.DataFrame:
    """
    Historical daily dislocation across venues. For each date: the cheapest and
    dearest venue and the spread between them in bps.
    """
    p = panel if panel is not None else daily_close_panel(asset, exchanges or USD_EXCHANGES, days)
    hi = p.max(axis=1)
    lo = p.min(axis=1)
    return pd.DataFrame({
        "cheapest": p.idxmin(axis=1),
        "dearest": p.idxmax(axis=1),
        "low": lo, "high": hi,
        "spread_bps": (hi / lo - 1.0) * 1e4,
    })


def dislocation_stats(spread_df: pd.DataFrame, fee_bps: float = 80.0) -> dict:
    """
    Summary of a cross-exchange spread series and how often it beat a round-trip
    cost of ``fee_bps`` (a proxy for two-venue taker fees).
    """
    s = spread_df["spread_bps"].dropna()
    return {
        "days": int(s.size),
        "mean_spread_bps": float(s.mean()),
        "median_spread_bps": float(s.median()),
        "p95_spread_bps": float(np.percentile(s, 95)),
        "max_spread_bps": float(s.max()),
        "pct_days_above_fees": float((s > fee_bps).mean() * 100.0),
        "fee_bps": fee_bps,
    }
