"""Market data — Finnhub WebSocket (real-time ticks) + REST bootstrap; yfinance for indices/futures/forex."""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
import websockets
import yfinance as yf

FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")
FH_REST = "https://finnhub.io/api/v1"
FH_WS   = "wss://ws.finnhub.io"

# Real-time via Finnhub WebSocket (free tier: up to 50 subscriptions)
WS_SYMBOLS = [
    # Mega-cap tech
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD",
    "AVGO", "ORCL", "CRM",  "ADBE",  "INTC", "QCOM", "NFLX",
    # ETFs
    "SPY",  "QQQ",  "IWM",  "DIA",  "GLD",  "TLT",  "HYG",  "EEM",
    "XLE",  "XLK",  "XLF",  "XLV",
    # Finance
    "JPM",  "GS",   "BAC",  "MS",   "V",    "MA",   "SCHW",
    # Healthcare / Energy / Consumer
    "UNH",  "LLY",  "ABBV", "XOM",  "CVX",  "COST", "WMT",  "HD",
    "MCD",  "NKE",  "AMGN", "JNJ",  "PFE",  "BA",   "CAT",
]

# Indices/futures/forex — yfinance only (Finnhub free tier doesn't cover these)
# Kept small (24 symbols) to avoid Yahoo Finance rate limits
YF_SYMBOLS = [
    "^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^FTSE", "^N225", "^HSI",
    "GC=F",  "CL=F", "BZ=F",  "SI=F", "HG=F", "NG=F",  "ZN=F",
    "DX-Y.NYB", "EURUSD=X", "JPY=X", "GBPUSD=X", "AUDUSD=X", "USDCAD=X", "BTC=F",
    "^TNX", "^IRX",
]

ALL_TICKERS = WS_SYMBOLS + YF_SYMBOLS

WATCHLIST = {
    "Indices": ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^FTSE", "^N225", "^HSI"],
    "ETFs":    ["SPY", "QQQ", "IWM", "GLD", "TLT", "HYG", "EEM", "XLE"],
    "Tech":    ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD"],
    "Macro":   ["GC=F", "CL=F", "BZ=F", "SI=F", "DX-Y.NYB", "EURUSD=X", "JPY=X"],
}

TICKER_NAMES = {
    "^GSPC": "S&P 500",    "^DJI":  "Dow Jones",   "^IXIC": "Nasdaq",
    "^RUT":  "Russell 2K", "^VIX":  "VIX",         "^FTSE": "FTSE 100",
    "^N225": "Nikkei 225", "^HSI":  "Hang Seng",
    "SPY":   "SPY",        "QQQ":   "QQQ",         "IWM":   "IWM",
    "DIA":   "DIA",        "GLD":   "Gold ETF",    "TLT":   "20Y Treasury",
    "HYG":   "High Yield", "EEM":   "Em. Mkts",    "XLE":   "Energy ETF",
    "XLK":   "Tech ETF",
    "AAPL":  "Apple",      "MSFT":  "Microsoft",   "NVDA":  "Nvidia",
    "GOOGL": "Alphabet",   "META":  "Meta",        "AMZN":  "Amazon",
    "TSLA":  "Tesla",      "AMD":   "AMD",         "AVGO":  "Broadcom",
    "ORCL":  "Oracle",
    "GC=F":  "Gold",       "CL=F":  "WTI Crude",   "BZ=F":  "Brent Crude",
    "SI=F":  "Silver",     "HG=F":  "Copper",      "NG=F":  "Nat Gas",
    "ZN=F":  "10Y T-Note",
    "^TNX":  "10Y Yield",  "^IRX":  "3M Yield",    "ZQ=F":  "FF Futures",
    "DX-Y.NYB": "USD Index", "EURUSD=X": "EUR/USD", "JPY=X": "USD/JPY",
    "GBPUSD=X": "GBP/USD",  "AUDUSD=X": "AUD/USD", "USDCAD=X": "USD/CAD",
    "BTC=F": "Bitcoin Fut",
}


@dataclass
class Quote:
    ticker:     str
    name:       str
    price:      float
    change:     float
    change_pct: float
    prev_close: float     = 0.0
    volume:     int       = 0
    market_cap: float     = 0.0
    day_high:   float     = 0.0
    day_low:    float     = 0.0
    updated:    float     = field(default_factory=time.time)

    @property
    def arrow(self) -> str:
        return "▲" if self.change >= 0 else "▼"

    @property
    def color(self) -> str:
        return "up" if self.change >= 0 else "down"


_store: dict[str, Quote] = {}
_tick_queues: list[asyncio.Queue] = []


def get_quotes() -> dict[str, Quote]:
    return dict(_store)


def subscribe_ticks() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _tick_queues.append(q)
    return q


def unsubscribe_ticks(q: asyncio.Queue) -> None:
    try:
        _tick_queues.remove(q)
    except ValueError:
        pass


def _broadcast(ticker: str, price: float) -> None:
    for q in _tick_queues:
        try:
            q.put_nowait({"s": ticker, "p": price})
        except asyncio.QueueFull:
            pass


async def fetch_quotes(tickers: list[str]) -> dict[str, Quote]:
    missing = [t for t in tickers if t not in _store]
    if missing:
        loop = asyncio.get_event_loop()
        fresh = await loop.run_in_executor(None, _yf_fetch, missing)
        _store.update(fresh)
    return {t: _store[t] for t in tickers if t in _store}


async def fetch_ticker_prices(tickers: list[str]) -> dict[str, float]:
    quotes = await fetch_quotes(tickers)
    return {t: q.price for t, q in quotes.items()}


# ── Finnhub REST — bootstrap initial quotes ───────────────────────────────────

async def _fh_quote(session: aiohttp.ClientSession, sym: str) -> Optional[Quote]:
    try:
        async with session.get(
            f"{FH_REST}/quote",
            params={"symbol": sym, "token": FINNHUB_KEY},
            timeout=aiohttp.ClientTimeout(total=5),
        ) as r:
            if r.status != 200:
                return None
            d = await r.json()
            price = float(d.get("c") or 0)
            pc    = float(d.get("pc") or price)
            if not price:
                return None
            return Quote(
                ticker=sym, name=TICKER_NAMES.get(sym, sym),
                price=price,
                change=price - pc,
                change_pct=((price - pc) / pc * 100) if pc else 0,
                prev_close=pc,
                day_high=float(d.get("h") or 0),
                day_low=float(d.get("l") or 0),
                updated=time.time(),
            )
    except Exception:
        return None


async def _fh_bootstrap(session: aiohttp.ClientSession):
    """Fetch all WS_SYMBOLS once via REST to populate prev_close/day_hi/lo before WS starts."""
    for sym in WS_SYMBOLS:
        q = await _fh_quote(session, sym)
        if q:
            _store[sym] = q
        await asyncio.sleep(1.1)


# ── Finnhub WebSocket — real-time trade ticks ─────────────────────────────────

async def _fh_ws_loop():
    """Subscribe to all WS_SYMBOLS; update _store on every trade tick."""
    url = f"{FH_WS}?token={FINNHUB_KEY}"
    while True:
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                for sym in WS_SYMBOLS:
                    await ws.send(json.dumps({"type": "subscribe", "symbol": sym}))
                async for raw in ws:
                    msg = json.loads(raw)
                    if msg.get("type") != "trade":
                        continue
                    for trade in msg.get("data", []):
                        sym   = trade.get("s")
                        price = float(trade.get("p") or 0)
                        vol   = int(trade.get("v") or 0)
                        if not sym or not price or sym not in _store:
                            continue
                        _broadcast(sym, price)
                        q = _store[sym]
                        _store[sym] = Quote(
                            ticker=q.ticker, name=q.name,
                            price=price,
                            change=price - q.prev_close,
                            change_pct=((price - q.prev_close) / q.prev_close * 100) if q.prev_close else 0,
                            prev_close=q.prev_close,
                            day_high=max(q.day_high, price) if q.day_high else price,
                            day_low=(min(q.day_low, price) if q.day_low else price),
                            volume=vol or q.volume,
                            updated=time.time(),
                        )
        except Exception:
            await asyncio.sleep(5)   # reconnect after brief pause


# ── yfinance — indices / futures / forex ─────────────────────────────────────

def _yf_fetch(tickers: list[str]) -> dict[str, Quote]:
    results = {}
    for t in tickers:
        try:
            info  = yf.Ticker(t).fast_info
            price = float(info.last_price or 0)
            prev  = float(info.previous_close or price)
            if not price:
                continue
            change = price - prev
            pct    = (change / prev * 100) if prev else 0
            results[t] = Quote(
                ticker=t,
                name=TICKER_NAMES.get(t, t),
                price=price,
                change=change,
                change_pct=pct,
                prev_close=prev,
                day_high=float(info.day_high or 0),
                day_low=float(info.day_low or 0),
                volume=int(getattr(info, "three_month_average_volume", 0) or 0),
            )
        except Exception:
            pass
    return results


async def _yf_loop(interval: int):
    while True:
        try:
            from feeds.yf_throttle import run as yf_run
            fresh = await yf_run(_yf_fetch, YF_SYMBOLS)
            _store.update(fresh)
        except Exception:
            pass
        await asyncio.sleep(interval)


# ── Forex bridge — populate EURUSD=X etc. from forex.py when yfinance is slow ──

FOREX_TICKER_MAP = {
    "EUR/USD": "EURUSD=X",
    "USD/JPY": "JPY=X",
    "GBP/USD": "GBPUSD=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
}

async def _forex_bridge_loop():
    """Populate EURUSD=X etc. from working forex.py (Frankfurter/ECB) data.
    Runs every 60s; yfinance _yf_loop will overwrite with futures prices when available."""
    while True:
        await asyncio.sleep(5)   # small delay to let _store settle after bootstrap
        try:
            from feeds.forex import get_forex
            fx = get_forex()
            for pair, ticker in FOREX_TICKER_MAP.items():
                v = (fx.rates or {}).get(pair)
                if not v:
                    continue
                rate = v.get("rate")
                prev = v.get("prev", rate)
                if not rate:
                    continue
                change = rate - prev if prev else 0
                pct    = (change / prev * 100) if prev else 0
                # Only update if yfinance hasn't populated this ticker recently
                existing = _store.get(ticker)
                if existing and (time.time() - existing.updated) < 700:
                    continue   # yfinance data is fresh — leave it
                _store[ticker] = Quote(
                    ticker=ticker, name=TICKER_NAMES.get(ticker, pair),
                    price=float(rate), change=float(change), change_pct=float(pct),
                    prev_close=float(prev) if prev else float(rate),
                )
        except Exception:
            pass
        await asyncio.sleep(60)


# ── Entry point ───────────────────────────────────────────────────────────────

async def run_poller(interval: int = 600):
    if FINNHUB_KEY:
        # Bootstrap REST first so prev_close/day_hi/lo are populated before WS starts
        async with aiohttp.ClientSession(headers={"User-Agent": "OpenBloomberg/1.0"}) as session:
            await _fh_bootstrap(session)
        # WebSocket for real-time ticks + yfinance for indices/futures (10 min refresh)
        # forex bridge provides FX pair fallback immediately
        await asyncio.gather(_fh_ws_loop(), _yf_loop(max(interval, 300)), _forex_bridge_loop())
    else:
        await asyncio.gather(_yf_loop(interval), _forex_bridge_loop())
