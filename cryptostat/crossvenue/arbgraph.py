"""
Multi-exchange (cross-venue) triangular / cyclic arbitrage.

Classic triangular arbitrage does a loop like USD -> BTC -> ETH -> USD entirely on
one exchange. This module generalizes it two ways:

  1. **Any-length cycles**, not just triangles (USD -> BTC -> ETH -> SOL -> USD).
  2. **Across many venues at once** — each leg of the loop may execute on whichever
     exchange offers the best rate. More venues = more edges = more chances for a
     profitable cycle. This is the "maximum exploitation" version, at the cost of
     latency and transfer risk (you must move assets between venues, and prices
     move while you do — so these are *measured* opportunities, not free money).

Model: a directed graph whose nodes are assets and whose edges are conversions
``X -> Y`` at an exchange's live rate, minus that venue's taker fee. A profitable
loop is a cycle whose edge rates multiply to > 1 — equivalently, a negative cycle
under weights ``w = -log(rate)`` (the textbook Bellman-Ford arbitrage view). The
graphs here are small, so cycles are enumerated directly, which also yields the
exact per-leg venue path.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import requests

from .exchanges import TAKER_FEE_BPS, USD_EXCHANGES

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "cryptostat/0.1"})


# --------------------------------------------------------------------------- #
# Symbol mapping for an arbitrary (base, quote) pair on each venue
# --------------------------------------------------------------------------- #
def _pair_symbol(base, quote, exchange):
    b, q = base.upper(), quote.upper()
    if exchange == "coinbase":
        return f"{b}-{q}"
    if exchange == "kraken":
        k = lambda a: "XBT" if a == "BTC" else a  # noqa: E731
        return f"{k(b)}{k(q)}"
    if exchange in ("bitstamp", "gemini"):
        return f"{b.lower()}{q.lower()}"
    if exchange == "bitfinex":
        return f"t{b}{q}"
    raise ValueError(exchange)


def _fetch_bidask(base, quote, exchange):
    """Best bid/ask for base/quote on one venue, or None if the pair isn't listed."""
    sym = _pair_symbol(base, quote, exchange)
    try:
        if exchange == "coinbase":
            d = _SESSION.get(f"https://api.exchange.coinbase.com/products/{sym}/ticker",
                             timeout=12).json()
            return float(d["bid"]), float(d["ask"])
        if exchange == "kraken":
            d = _SESSION.get("https://api.kraken.com/0/public/Ticker",
                             params={"pair": sym}, timeout=12).json()
            if d.get("error"):
                return None
            k = next(iter(d["result"]))
            return float(d["result"][k]["b"][0]), float(d["result"][k]["a"][0])
        if exchange == "bitstamp":
            d = _SESSION.get(f"https://www.bitstamp.net/api/v2/ticker/{sym}/", timeout=12).json()
            if "bid" not in d:
                return None
            return float(d["bid"]), float(d["ask"])
        if exchange == "gemini":
            d = _SESSION.get(f"https://api.gemini.com/v1/pubticker/{sym}", timeout=12).json()
            if "bid" not in d:
                return None
            return float(d["bid"]), float(d["ask"])
        if exchange == "bitfinex":
            d = _SESSION.get(f"https://api-pub.bitfinex.com/v2/ticker/{sym}", timeout=12).json()
            if not isinstance(d, list) or len(d) < 4:
                return None
            return float(d[0]), float(d[2])
    except Exception:  # noqa: BLE001 — unlisted pair / transient error => no edge
        return None
    return None


# --------------------------------------------------------------------------- #
# Build the conversion-rate edge set
# --------------------------------------------------------------------------- #
@dataclass
class Edge:
    frm: str
    to: str
    exchange: str
    rate_gross: float     # units of `to` per unit of `frm`, before fees
    rate_net: float       # after the venue's taker fee


def build_edges(assets=("USD", "BTC", "ETH", "SOL", "LTC"),
                exchanges=None, quotes=("USD", "BTC"), pace=0.12):
    """
    Fetch live quotes and build directed conversion edges across all venues.

    For each listed pair base/quote on each exchange, two edges are created:
      * quote -> base  (buy base at the ask): rate = 1/ask
      * base  -> quote (sell base at the bid): rate = bid
    each multiplied by (1 - taker_fee) for that venue.
    """
    exchanges = list(exchanges or USD_EXCHANGES)
    assets = list(assets)
    edges = []
    for ex in exchanges:
        fee = TAKER_FEE_BPS.get(ex, 0) / 1e4
        for q in quotes:
            for base in assets:
                if base == q or q not in assets:
                    continue
                ba = _fetch_bidask(base, q, ex)
                time.sleep(pace)
                if not ba:
                    continue
                bid, ask = ba
                if bid <= 0 or ask <= 0:
                    continue
                # quote -> base  (spend quote, buy base at ask)
                edges.append(Edge(q, base, ex, 1.0 / ask, (1.0 / ask) * (1 - fee)))
                # base -> quote  (sell base at bid, receive quote)
                edges.append(Edge(base, q, ex, bid, bid * (1 - fee)))
    return edges


# --------------------------------------------------------------------------- #
# Cycle search
# --------------------------------------------------------------------------- #
@dataclass
class Cycle:
    path: list          # [asset0, asset1, ..., asset0]
    legs: list          # [(frm, to, exchange, rate_net), ...]
    gross_return: float # product of gross rates - 1
    net_return: float   # product of net rates - 1  (this is the real number)

    def multi_venue(self) -> bool:
        return len({leg[2] for leg in self.legs}) > 1


def _best_rate_map(edges, single_exchange=None):
    """For each (frm,to) keep the best NET edge (optionally within one venue)."""
    best = {}
    for e in edges:
        if single_exchange and e.exchange != single_exchange:
            continue
        key = (e.frm, e.to)
        if key not in best or e.rate_net > best[key].rate_net:
            best[key] = e
    return best


def find_cycles(edges, base="USD", max_len=4, single_exchange=None):
    """
    Enumerate simple cycles base -> ... -> base (length <= max_len) and return
    them sorted by net return, best first. ``single_exchange`` restricts every
    leg to one venue (classic single-venue triangular).
    """
    best = _best_rate_map(edges, single_exchange)
    assets = {a for k in best for a in k}
    results = []

    def dfs(node, gross, net, legs, visited):
        if legs and node == base:
            results.append(Cycle([base] + [l[1] for l in legs], list(legs),
                                 gross - 1.0, net - 1.0))
            return
        if len(legs) >= max_len:
            return
        for nxt in assets:
            e = best.get((node, nxt))
            if e is None:
                continue
            if nxt == base:
                dfs(base, gross * e.rate_gross, net * e.rate_net,
                    legs + [(node, nxt, e.exchange, e.rate_net)], visited)
            elif nxt not in visited:
                dfs(nxt, gross * e.rate_gross, net * e.rate_net,
                    legs + [(node, nxt, e.exchange, e.rate_net)], visited | {nxt})

    dfs(base, 1.0, 1.0, [], {base})
    results.sort(key=lambda c: c.net_return, reverse=True)
    return results


def scan(assets=("USD", "BTC", "ETH", "SOL", "LTC"), exchanges=None,
         base="USD", max_len=4, quotes=("USD", "BTC")):
    """
    One-shot scan. Returns a dict with the best MULTI-venue cycle (each leg on its
    best exchange) and the best SINGLE-venue cycle (all legs on one exchange), so
    you can see exactly what trading across sources buys you.
    """
    edges = build_edges(assets, exchanges, quotes)
    multi = find_cycles(edges, base, max_len, single_exchange=None)
    per_ex = {}
    for ex in (exchanges or USD_EXCHANGES):
        cyc = find_cycles(edges, base, max_len, single_exchange=ex)
        if cyc:
            per_ex[ex] = cyc[0]
    best_single = max(per_ex.values(), key=lambda c: c.net_return, default=None)
    return {
        "edges": edges,
        "best_multi": multi[0] if multi else None,
        "all_multi": multi,
        "best_single": best_single,
        "per_exchange": per_ex,
    }
