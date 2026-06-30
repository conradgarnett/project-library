"""Price chart data — intraday (5m, 1 day) and daily (1d, 6 months) OHLCV bars.
Uses yfinance via the global yf_throttle (serialised, 350ms gap between calls).
Falls back to Polygon.io if POLYGON_KEY is set and yfinance fails.
"""
import asyncio
import os
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

POLYGON_KEY  = os.environ.get("POLYGON_KEY", "")
POLYGON_BASE = "https://api.polygon.io/v2/aggs/ticker"

CHART_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META",
    "AMZN", "TSLA", "AMD",  "AVGO",  "ORCL",
    "SPY",  "QQQ",  "GLD",  "TLT",   "XLK",  "XLE",
]


@dataclass
class ChartsState:
    intraday: dict = field(default_factory=dict)
    daily:    dict = field(default_factory=dict)
    updated:  float = 0.0
    error:    Optional[str] = None


_state = ChartsState()


def get_charts() -> ChartsState:
    return _state


# ── yfinance helpers (run in executor via throttle) ───────────────────────────

def _yf_intraday(symbol: str) -> list:
    import yfinance as yf
    df = yf.Ticker(symbol).history(period="1d", interval="5m")
    if df.empty:
        return []
    return [{"t": int(ts.timestamp()), "o": round(float(r["Open"]),4),
             "h": round(float(r["High"]),4), "l": round(float(r["Low"]),4),
             "c": round(float(r["Close"]),4), "v": int(r["Volume"])}
            for ts, r in df.iterrows()]


def _yf_daily(symbol: str) -> list:
    import yfinance as yf
    df = yf.Ticker(symbol).history(period="6mo", interval="1d")
    if df.empty:
        return []
    return [{"t": int(ts.timestamp()), "o": round(float(r["Open"]),4),
             "h": round(float(r["High"]),4), "l": round(float(r["Low"]),4),
             "c": round(float(r["Close"]),4), "v": int(r["Volume"])}
            for ts, r in df.iterrows()]


# ── Polygon fallback ──────────────────────────────────────────────────────────

import aiohttp

async def _polygon_bars(session: aiohttp.ClientSession, symbol: str,
                         multiplier: int, timespan: str,
                         from_date: str, to_date: str,
                         limit: int = 500) -> list:
    url = f"{POLYGON_BASE}/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}"
    try:
        async with session.get(
            url,
            params={"limit": limit, "adjusted": "true", "apiKey": POLYGON_KEY},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as r:
            if r.status == 429:
                await asyncio.sleep(12)
                return []
            if r.status != 200:
                return []
            d = await r.json()
            return [
                {"t": int(b["t"]/1000), "o": round(b["o"],4),
                 "h": round(b["h"],4), "l": round(b["l"],4),
                 "c": round(b["c"],4), "v": int(b.get("v",0))}
                for b in (d.get("results") or [])
            ]
    except Exception:
        return []


# ── on-demand per-symbol fetch (used by /api/charts/{symbol}) ────────────────

def _fetch_one_blocking(symbol: str) -> tuple[list, list]:
    intraday: list = []
    daily:    list = []
    try:
        intraday = _yf_intraday(symbol)
    except Exception:
        pass
    try:
        daily = _yf_daily(symbol)
    except Exception:
        pass
    if not intraday and POLYGON_KEY:
        import urllib.request, json as _json
        today      = date.today().isoformat()
        intra_from = (date.today() - timedelta(days=5)).isoformat()
        daily_from = (date.today() - timedelta(days=185)).isoformat()
        try:
            url = f"{POLYGON_BASE}/{symbol}/range/5/minute/{intra_from}/{today}?limit=500&adjusted=true&apiKey={POLYGON_KEY}"
            d = _json.loads(urllib.request.urlopen(url, timeout=15).read())
            intraday = [{"t": int(b["t"]/1000), "o": round(b["o"],4), "h": round(b["h"],4),
                         "l": round(b["l"],4), "c": round(b["c"],4), "v": int(b.get("v",0))}
                        for b in (d.get("results") or [])]
        except Exception:
            pass
        try:
            url = f"{POLYGON_BASE}/{symbol}/range/1/day/{daily_from}/{today}?limit=200&adjusted=true&apiKey={POLYGON_KEY}"
            d = _json.loads(urllib.request.urlopen(url, timeout=15).read())
            daily = [{"t": int(b["t"]/1000), "o": round(b["o"],4), "h": round(b["h"],4),
                      "l": round(b["l"],4), "c": round(b["c"],4), "v": int(b.get("v",0))}
                     for b in (d.get("results") or [])]
        except Exception:
            pass
    return intraday, daily


# ── poller ────────────────────────────────────────────────────────────────────

async def run_poller(interval: int = 300):
    global _state
    from feeds.yf_throttle import run as yf_run

    while True:
        intraday: dict = {}
        daily:    dict = {}
        errors = 0

        for sym in CHART_SYMBOLS:
            try:
                bars = await yf_run(_yf_intraday, sym)
                if bars:
                    intraday[sym] = bars
            except Exception:
                errors += 1

            try:
                bars = await yf_run(_yf_daily, sym)
                if bars:
                    daily[sym] = bars
            except Exception:
                errors += 1

        if intraday or daily:
            _state.intraday = intraday
            _state.daily    = daily
            _state.updated  = time.time()
            _state.error    = None
        elif errors > len(CHART_SYMBOLS):
            # All yfinance calls failed — try Polygon fallback if available
            if POLYGON_KEY:
                today      = date.today().isoformat()
                intra_from = (date.today() - timedelta(days=5)).isoformat()
                daily_from = (date.today() - timedelta(days=185)).isoformat()
                async with aiohttp.ClientSession(headers={"User-Agent": "OpenBloomberg/1.0"}) as session:
                    for sym in CHART_SYMBOLS:
                        bars = await _polygon_bars(session, sym, 1, "day", daily_from, today, 200)
                        if bars:
                            daily[sym] = bars
                        await asyncio.sleep(12)
                        bars = await _polygon_bars(session, sym, 5, "minute", intra_from, today, 500)
                        if bars:
                            intraday[sym] = bars
                        await asyncio.sleep(12)
                if intraday or daily:
                    _state.intraday = intraday
                    _state.daily    = daily
                    _state.updated  = time.time()
                    _state.error    = None
            else:
                _state.error = "yfinance rate limited and no POLYGON_KEY fallback"

        await asyncio.sleep(interval)
