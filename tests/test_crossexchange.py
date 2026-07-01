"""Cross-exchange arbitrage math — validated offline on synthetic quotes/panels."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402

from cryptostat.crossexchange import (  # noqa: E402
    cross_exchange_spread,
    dislocation_stats,
    live_arbitrage,
)


def _quotes(prices):
    # prices: {exchange: (bid, ask)}
    rows = [{"exchange": k, "bid": v[0], "ask": v[1], "mid": 0.5 * sum(v)}
            for k, v in prices.items()]
    return pd.DataFrame(rows).set_index("exchange")


def test_live_arbitrage_finds_best_route_no_fees():
    # Cheapest ask on B (100), highest bid on A (105) -> buy B, sell A.
    q = _quotes({"A": (105, 106), "B": (99, 100)})
    best, table = live_arbitrage("X", quotes=q, use_fees=False)
    assert best.buy_on == "B" and best.sell_on == "A"
    assert abs(best.gross_bps - (105 - 100) / 100 * 1e4) < 1e-6
    assert best.net_bps == best.gross_bps       # no fees


def test_live_arbitrage_fees_can_erase_edge():
    # ~20 bps gross edge, but real venue taker fees (kraken 26 + coinbase 60)
    # swamp it. Uses real venue names so the fee lookup applies.
    q = _quotes({"kraken": (999, 1000), "coinbase": (1002, 1003)})
    best, _ = live_arbitrage("X", quotes=q, use_fees=True)
    assert best.net_bps < best.gross_bps
    assert best.net_bps < 0


def test_efficient_market_has_no_positive_edge():
    q = _quotes({"coinbase": (100.0, 100.1), "kraken": (100.0, 100.1),
                 "gemini": (99.99, 100.11)})
    best, _ = live_arbitrage("X", quotes=q, use_fees=True)
    assert best.net_bps < 0


def test_cross_exchange_spread_and_stats():
    idx = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    panel = pd.DataFrame({
        "ex1": [100, 100, 100, 100, 100.0],
        "ex2": [101, 100, 100, 100, 103.0],   # ex2 dear on day 0 (100 bps) and day 4 (300 bps)
    }, index=idx)
    sp = cross_exchange_spread("X", panel=panel)
    assert abs(sp["spread_bps"].iloc[0] - 100.0) < 1e-6
    assert sp["dearest"].iloc[0] == "ex2" and sp["dearest"].iloc[4] == "ex2"
    stats = dislocation_stats(sp, fee_bps=150)
    # only day 4 (300 bps) beats a 150 bps round-trip cost -> 1/5 = 20%
    assert abs(stats["pct_days_above_fees"] - 20.0) < 1e-6
    assert stats["max_spread_bps"] > 290


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    fails = 0
    for fn in fns:
        try:
            fn(); print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            fails += 1; print(f"FAIL  {fn.__name__}: {e}")
    print(f"\n{len(fns) - fails}/{len(fns)} passed")
    sys.exit(1 if fails else 0)
