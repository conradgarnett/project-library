"""Polygon.io / massive.com — daily OHLCV bars (1 year) + company fundamentals."""

import asyncio
import aiohttp
import time
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

POLYGON_KEY = os.environ.get("POLYGON_KEY", "")
BASE = "https://api.massive.com"

SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META",
    "AMZN", "TSLA", "AMD",  "AVGO",  "ORCL",
    "SPY",  "QQQ",  "GLD",  "TLT",   "XLK",  "XLE",
    "JPM",  "V",    "UNH",  "BRK.B", "JNJ",  "WMT",
    "BAC",  "XOM",  "CVX",  "PG",    "MA",   "HD",
]


@dataclass
class PolygonState:
    bars:         dict = field(default_factory=dict)   # symbol → [{t,o,h,l,c,v}]
    fundamentals: dict = field(default_factory=dict)   # symbol → company details
    updated:      float = 0.0
    error:        Optional[str] = None


_state = PolygonState()


def get_polygon() -> PolygonState:
    return _state


async def _fetch_bars(session: aiohttp.ClientSession, symbol: str,
                      from_date: str, to_date: str) -> list:
    url = (f"{BASE}/v2/aggs/ticker/{symbol}/range/1/day/{from_date}/{to_date}"
           f"?adjusted=true&sort=asc&limit=365")
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                d = await r.json()
                return [
                    {"t": b["t"] // 1000, "o": b["o"], "h": b["h"],
                     "l": b["l"], "c": b["c"], "v": int(b.get("v", 0))}
                    for b in d.get("results", [])
                ]
    except Exception:
        pass
    return []


async def _fetch_fundamentals(session: aiohttp.ClientSession, symbol: str) -> dict:
    url = f"{BASE}/v3/reference/tickers/{symbol}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                d = await r.json()
                return d.get("results", {})
    except Exception:
        pass
    return {}


async def _fetch_all(session: aiohttp.ClientSession) -> None:
    global _state
    today = date.today()
    from_date = (today - timedelta(days=365)).isoformat()
    to_date = today.isoformat()

    bars: dict = {}
    fundamentals: dict = {}

    for sym in SYMBOLS:
        b, f = await asyncio.gather(
            _fetch_bars(session, sym, from_date, to_date),
            _fetch_fundamentals(session, sym),
        )
        if b:
            bars[sym] = b
        if f:
            fundamentals[sym] = f
        await asyncio.sleep(0.25)  # ~4 symbol-pairs/sec → 8 req/sec, within free limits

    _state.bars = bars
    _state.fundamentals = fundamentals
    _state.updated = time.time()
    _state.error = None


async def run_poller(interval: int = 3600):
    if not POLYGON_KEY:
        _state.error = "No POLYGON_KEY"
        return
    headers = {"Authorization": f"Bearer {POLYGON_KEY}"}
    async with aiohttp.ClientSession(headers=headers) as session:
        while True:
            try:
                await _fetch_all(session)
            except Exception as e:
                _state.error = str(e)
            await asyncio.sleep(interval)
