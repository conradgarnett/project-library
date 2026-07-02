"""Cross-venue cyclic arbitrage graph — cycle math validated offline."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptostat.crossvenue.arbgraph import Edge, find_cycles  # noqa: E402


def _edge(frm, to, ex, rate):
    return Edge(frm, to, ex, rate, rate)      # fee-free (gross == net) for clean math


# A deliberate arbitrage: USD->BTC->ETH->USD multiplies to 1.20 (+20%).
ARB_EDGES = [
    _edge("USD", "BTC", "exA", 2e-5),         # 1 BTC = $50,000
    _edge("BTC", "ETH", "exA", 20.0),         # 1 BTC = 20 ETH
    _edge("ETH", "USD", "exB", 3000.0),       # 1 ETH = $3,000  (cross-venue leg)
    _edge("BTC", "USD", "exA", 50000.0),
    _edge("ETH", "BTC", "exA", 0.05),
    _edge("USD", "ETH", "exB", 1 / 3000.0),
]


def test_finds_known_arbitrage_cycle():
    cycles = find_cycles(ARB_EDGES, base="USD", max_len=3)
    best = cycles[0]
    assert best.path == ["USD", "BTC", "ETH", "USD"]
    assert abs(best.net_return - 0.20) < 1e-6
    assert best.multi_venue()                 # legs span exA and exB


def test_no_arbitrage_when_rates_consistent():
    # Consistent rates: every loop multiplies to ~1, no profit.
    edges = [
        _edge("USD", "BTC", "exA", 2e-5), _edge("BTC", "USD", "exA", 50000.0),
        _edge("USD", "ETH", "exA", 1 / 3000.0), _edge("ETH", "USD", "exA", 3000.0),
        _edge("BTC", "ETH", "exA", 50000 / 3000.0), _edge("ETH", "BTC", "exA", 3000 / 50000.0),
    ]
    best = find_cycles(edges, base="USD", max_len=3)[0]
    assert best.net_return < 1e-9


def test_single_exchange_constraint_excludes_cross_venue_arb():
    # The profitable cycle needs exB's ETH->USD leg; within exA alone there is none.
    only_a = find_cycles(ARB_EDGES, base="USD", max_len=3, single_exchange="exA")
    assert all(c.net_return <= 1e-9 for c in only_a)


def test_fees_reduce_net_below_gross():
    edges = [
        Edge("USD", "BTC", "exA", 2e-5, 2e-5 * 0.998),
        Edge("BTC", "ETH", "exA", 20.0, 20.0 * 0.998),
        Edge("ETH", "USD", "exB", 3000.0, 3000.0 * 0.998),
    ]
    best = find_cycles(edges, base="USD", max_len=3)[0]
    assert best.net_return < best.gross_return


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
