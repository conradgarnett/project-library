"""
Data for the allocator — free daily returns, no API key.

Fetches daily close prices from Coinbase (same free source as the sibling crypto
projects) and converts to a returns panel. The allocator itself is return-stream
agnostic: the columns can just as well be *your own strategies'* daily returns
(funding carry, stat-arb) loaded from a CSV — that is the multi-strategy use case.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "portlib/0.1"})

DEFAULT_UNIVERSE = ["BTC-USD", "ETH-USD", "SOL-USD", "LTC-USD", "LINK-USD",
                    "BCH-USD", "AVAX-USD", "ADA-USD", "XLM-USD", "DOT-USD"]


def _fetch_coinbase_daily(symbol, days):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    url = f"https://api.exchange.coinbase.com/products/{symbol}/candles"
    rows, win, cur = [], timedelta(seconds=86400 * 300), end
    while cur > start:
        cs = max(start, cur - win)
        r = _SESSION.get(url, params={"granularity": 86400, "start": cs.isoformat(),
                                      "end": cur.isoformat()}, timeout=20)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        cur = cs
        time.sleep(0.34)
    if not rows:
        raise RuntimeError(f"no candles for {symbol}")
    df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "vol"])
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df.drop_duplicates("time").set_index("time").sort_index()["close"].astype(float)


def price_panel(symbols=None, days=730, force_refresh=False) -> pd.DataFrame:
    """Aligned daily close prices for a universe (cached to data/)."""
    symbols = symbols or DEFAULT_UNIVERSE
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache = os.path.join(CACHE_DIR, f"prices_{days}d.csv")
    if os.path.exists(cache) and not force_refresh:
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        if set(symbols).issubset(df.columns):
            return df[symbols].dropna(how="all")
    series = {}
    for s in symbols:
        try:
            series[s] = _fetch_coinbase_daily(s, days).rename(s)
        except Exception as e:  # noqa: BLE001
            print(f"  [skip {s}] {type(e).__name__}: {e}")
    panel = pd.concat(series.values(), axis=1, join="inner").dropna(how="all")
    panel.to_csv(cache)
    return panel


def returns_panel(symbols=None, days=730, force_refresh=False) -> pd.DataFrame:
    """Daily simple returns for a universe (drops the first NaN row)."""
    return price_panel(symbols, days, force_refresh).pct_change().dropna()


def load_returns_csv(path: str) -> pd.DataFrame:
    """
    Load a returns panel from CSV (first column a date index, other columns are
    per-asset OR per-strategy return series). This is how you feed your own
    strategy returns into the allocator.
    """
    return pd.read_csv(path, index_col=0, parse_dates=True).dropna()
