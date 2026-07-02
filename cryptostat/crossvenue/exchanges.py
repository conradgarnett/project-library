"""
Multi-exchange data layer — the same asset, priced on many venues.

Cross-exchange arbitrage needs one thing the single-venue data layer doesn't:
the *same* coin's price from several exchanges at once. This module provides a
unified interface over five free, key-less USD spot venues:

    coinbase, kraken, bitstamp, gemini, bitfinex

Each exposes:
  * daily close history  → ``daily_close(asset, exchange, days)``
  * a live bid/ask quote → ``live_ticker(asset, exchange)``

and there are panel helpers that stack all venues together:
  * ``daily_close_panel(asset, exchanges, days)`` — aligned close prices
  * ``live_quote_panel(asset, exchanges)`` — current bid/ask/mid per venue

All venues quote in USD so prices are directly comparable (no stablecoin basis).
"""

from __future__ import annotations

import time

import pandas as pd
import requests

USD_EXCHANGES = ["coinbase", "kraken", "bitstamp", "gemini", "bitfinex"]

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "cryptostat/0.1"})

# Per-exchange taker fees (bps) — public standard-tier rates, approximate.
TAKER_FEE_BPS = {"coinbase": 60, "kraken": 26, "bitstamp": 40, "gemini": 40, "bitfinex": 20}


# --------------------------------------------------------------------------- #
# Symbol mapping — normalize an asset ("BTC") to each venue's product id.
# --------------------------------------------------------------------------- #
def _symbol(asset: str, exchange: str) -> str:
    a = asset.upper()
    if exchange == "coinbase":
        return f"{a}-USD"
    if exchange == "kraken":
        return f"{'XBT' if a == 'BTC' else a}USD"
    if exchange in ("bitstamp", "gemini"):
        return f"{a.lower()}usd"
    if exchange == "bitfinex":
        return f"t{a}USD"
    raise ValueError(f"unknown exchange {exchange!r}")


# --------------------------------------------------------------------------- #
# Daily close history (one call each; recent history, no pagination)
# --------------------------------------------------------------------------- #
def daily_close(asset: str, exchange: str, days: int = 365) -> pd.Series:
    """Daily close prices for ``asset`` on ``exchange``, indexed by UTC date."""
    sym = _symbol(asset, exchange)
    if exchange == "coinbase":
        r = _SESSION.get(f"https://api.exchange.coinbase.com/products/{sym}/candles",
                         params={"granularity": 86400}, timeout=20).json()
        idx = [pd.to_datetime(row[0], unit="s", utc=True) for row in r]
        close = [row[4] for row in r]
    elif exchange == "kraken":
        r = _SESSION.get("https://api.kraken.com/0/public/OHLC",
                         params={"pair": sym, "interval": 1440}, timeout=20).json()
        key = next(k for k in r["result"] if k != "last")
        rows = r["result"][key]
        idx = [pd.to_datetime(int(row[0]), unit="s", utc=True) for row in rows]
        close = [float(row[4]) for row in rows]
    elif exchange == "bitstamp":
        r = _SESSION.get(f"https://www.bitstamp.net/api/v2/ohlc/{sym}/",
                         params={"step": 86400, "limit": 1000}, timeout=20).json()
        rows = r["data"]["ohlc"]
        idx = [pd.to_datetime(int(row["timestamp"]), unit="s", utc=True) for row in rows]
        close = [float(row["close"]) for row in rows]
    elif exchange == "gemini":
        r = _SESSION.get(f"https://api.gemini.com/v2/candles/{sym}/1day", timeout=20).json()
        if not isinstance(r, list) or not r or not isinstance(r[0], list):
            raise RuntimeError(f"gemini bad/rate-limited response: {str(r)[:80]}")
        idx = [pd.to_datetime(row[0], unit="ms", utc=True) for row in r]
        close = [row[4] for row in r]           # [time, open, high, low, close, vol]
    elif exchange == "bitfinex":
        r = _SESSION.get(f"https://api-pub.bitfinex.com/v2/candles/trade:1D:{sym}/hist",
                         params={"limit": 1000}, timeout=20).json()
        if not isinstance(r, list) or not r or not isinstance(r[0], list):
            raise RuntimeError(f"bitfinex bad/rate-limited response: {str(r)[:80]}")
        idx = [pd.to_datetime(row[0], unit="ms", utc=True) for row in r]
        close = [row[2] for row in r]           # [time, open, CLOSE, high, low, vol]
    else:
        raise ValueError(f"unknown exchange {exchange!r}")

    s = pd.Series(close, index=idx, dtype=float, name=exchange)
    s.index = s.index.normalize()               # align on the date
    return s[~s.index.duplicated(keep="last")].sort_index()


def daily_close_panel(asset: str, exchanges=None, days: int = 365, how="inner") -> pd.DataFrame:
    """Aligned daily-close panel: one column per exchange for the same asset."""
    exchanges = exchanges or USD_EXCHANGES
    series = {}
    for ex in exchanges:
        for attempt in range(2):               # one retry for transient rate limits
            try:
                series[ex] = daily_close(asset, ex, days)
                break
            except Exception as e:  # noqa: BLE001 — a flaky venue shouldn't sink the panel
                if attempt == 0:
                    time.sleep(0.6)
                    continue
                print(f"  [skip {ex}] {type(e).__name__}: {e}")
        time.sleep(0.15)
    if not series:
        raise RuntimeError(f"no exchange returned data for {asset}")
    panel = pd.concat(series.values(), axis=1, join=how)
    return panel.tail(days).dropna(how="all")


# --------------------------------------------------------------------------- #
# Live bid/ask quotes
# --------------------------------------------------------------------------- #
def live_ticker(asset: str, exchange: str) -> dict:
    """Current best bid/ask/mid for ``asset`` on ``exchange``."""
    sym = _symbol(asset, exchange)
    if exchange == "coinbase":
        d = _SESSION.get(f"https://api.exchange.coinbase.com/products/{sym}/ticker",
                         timeout=15).json()
        bid, ask = float(d["bid"]), float(d["ask"])
    elif exchange == "kraken":
        d = _SESSION.get("https://api.kraken.com/0/public/Ticker",
                         params={"pair": sym}, timeout=15).json()
        k = next(iter(d["result"]))
        bid, ask = float(d["result"][k]["b"][0]), float(d["result"][k]["a"][0])
    elif exchange == "bitstamp":
        d = _SESSION.get(f"https://www.bitstamp.net/api/v2/ticker/{sym}/", timeout=15).json()
        bid, ask = float(d["bid"]), float(d["ask"])
    elif exchange == "gemini":
        d = _SESSION.get(f"https://api.gemini.com/v1/pubticker/{sym}", timeout=15).json()
        bid, ask = float(d["bid"]), float(d["ask"])
    elif exchange == "bitfinex":
        d = _SESSION.get(f"https://api-pub.bitfinex.com/v2/ticker/{sym}", timeout=15).json()
        bid, ask = float(d[0]), float(d[2])     # [BID, BID_SZ, ASK, ASK_SZ, ...]
    else:
        raise ValueError(f"unknown exchange {exchange!r}")
    return {"exchange": exchange, "bid": bid, "ask": ask, "mid": 0.5 * (bid + ask)}


def live_quote_panel(asset: str, exchanges=None) -> pd.DataFrame:
    """Current bid/ask/mid for ``asset`` across venues, one row per exchange."""
    exchanges = exchanges or USD_EXCHANGES
    rows = []
    for ex in exchanges:
        for attempt in range(2):               # one retry for transient rate limits
            try:
                rows.append(live_ticker(asset, ex))
                break
            except Exception as e:  # noqa: BLE001
                if attempt == 0:
                    time.sleep(0.4)
                    continue
                print(f"  [skip {ex}] {type(e).__name__}: {e}")
        time.sleep(0.12)                        # be polite between venues
    return pd.DataFrame(rows).set_index("exchange")
