"""
Crypto market-data layer — free, key-less exchange REST APIs with on-disk caching.

Primary source is **Coinbase** (deep USD-pair history, paginated); **Kraken** is
available as a second venue (useful for the cross-exchange extension and for
recent data). No API keys, no paid feeds — the whole point of doing stat-arb on
crypto instead of equities.

    from cryptostat.data import fetch_ohlcv, price_panel
    df = fetch_ohlcv("BTC-USD", exchange="coinbase", granularity="1d", days=730)
    panel = price_panel(["BTC-USD", "ETH-USD", "SOL-USD"], days=730)

Data is cached under ``data/`` (git-ignored); pass ``force_refresh=True`` to
re-download.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

_COINBASE_GRAN = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "6h": 21600, "1d": 86400}
_KRAKEN_INT = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440, "1w": 10080}

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "cryptostat/0.1"})


def _cache_path(exchange, symbol, granularity):
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = symbol.replace("/", "-")
    return os.path.join(CACHE_DIR, f"{exchange}_{safe}_{granularity}.csv")


# --------------------------------------------------------------------------- #
# Coinbase
# --------------------------------------------------------------------------- #
def _fetch_coinbase(symbol, granularity, days):
    gran = _COINBASE_GRAN[granularity]
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    url = f"https://api.exchange.coinbase.com/products/{symbol}/candles"

    rows = []
    win = timedelta(seconds=gran * 300)     # Coinbase caps at 300 candles/request
    cur_end = end
    while cur_end > start:
        cur_start = max(start, cur_end - win)
        resp = _SESSION.get(url, params={
            "granularity": gran,
            "start": cur_start.isoformat(),
            "end": cur_end.isoformat(),
        }, timeout=20)
        resp.raise_for_status()
        batch = resp.json()             # [[time, low, high, open, close, volume], ...]
        if not batch:
            break
        rows.extend(batch)
        cur_end = cur_start
        time.sleep(0.34)                # be polite to the public endpoint

    if not rows:
        raise RuntimeError(f"no Coinbase candles returned for {symbol}")
    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df = df.drop_duplicates("time").set_index("time").sort_index()
    return df[["open", "high", "low", "close", "volume"]].astype(float)


# --------------------------------------------------------------------------- #
# Kraken
# --------------------------------------------------------------------------- #
def _fetch_kraken(symbol, granularity, days):
    interval = _KRAKEN_INT[granularity]
    since = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
    resp = _SESSION.get("https://api.kraken.com/0/public/OHLC",
                        params={"pair": symbol, "interval": interval, "since": since},
                        timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("error"):
        raise RuntimeError(f"Kraken error for {symbol}: {payload['error']}")
    result = payload["result"]
    key = next(k for k in result if k != "last")
    cols = ["time", "open", "high", "low", "close", "vwap", "volume", "count"]
    df = pd.DataFrame(result[key], columns=cols)
    df["time"] = pd.to_datetime(df["time"].astype(int), unit="s", utc=True)
    df = df.set_index("time").sort_index()
    return df[["open", "high", "low", "close", "volume"]].astype(float)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def fetch_ohlcv(symbol, exchange="coinbase", granularity="1d", days=730,
                force_refresh=False) -> pd.DataFrame:
    """
    Fetch OHLCV candles for one symbol, cached to ``data/``.

    exchange    : "coinbase" (default, deep history) or "kraken".
    granularity : "1m","5m","15m","1h","6h"/"4h","1d","1w" (venue-dependent).
    days        : how far back to request.
    """
    path = _cache_path(exchange, symbol, granularity)
    if os.path.exists(path) and not force_refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)

    if exchange == "coinbase":
        df = _fetch_coinbase(symbol, granularity, days)
    elif exchange == "kraken":
        df = _fetch_kraken(symbol, granularity, days)
    else:
        raise ValueError("exchange must be 'coinbase' or 'kraken'")
    df.to_csv(path)
    return df


def price_panel(symbols, exchange="coinbase", granularity="1d", days=730,
                field="close", how="inner", force_refresh=False) -> pd.DataFrame:
    """
    Aligned price panel (one column per symbol) for a universe.

    how="inner" keeps only timestamps present for every symbol (clean for
    cointegration); "outer" keeps the union and forward-fills gaps.
    """
    series = {}
    for sym in symbols:
        try:
            df = fetch_ohlcv(sym, exchange, granularity, days, force_refresh)
            series[sym] = df[field].rename(sym)
        except Exception as e:  # noqa: BLE001 — skip a bad symbol, keep the panel
            print(f"  [skip {sym}] {type(e).__name__}: {e}")
    if not series:
        raise RuntimeError("no symbols fetched")
    panel = pd.concat(series.values(), axis=1, join=how)
    if how == "outer":
        panel = panel.ffill()
    return panel.dropna(how="all")


# A reasonable, liquid default universe of Coinbase USD pairs to start from.
DEFAULT_UNIVERSE = [
    "BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "AVAX-USD", "DOT-USD",
    "LINK-USD", "LTC-USD", "BCH-USD", "XLM-USD", "ATOM-USD", "ETC-USD",
    "UNI-USD", "AAVE-USD", "MATIC-USD", "ALGO-USD", "XTZ-USD", "FIL-USD",
]
