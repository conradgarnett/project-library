"""Market data via yfinance (Yahoo Finance) — no API key required."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import yfinance as yf

WATCHLIST = {
    "Indices": ["^GSPC", "^DJI", "^IXIC", "^RUT", "^VIX", "^FTSE", "^N225", "^HSI"],
    "ETFs":    ["SPY", "QQQ", "IWM", "GLD", "TLT", "HYG", "EEM", "XLE"],
    "Tech":    ["AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD"],
    "Macro":   ["BTC-USD", "ETH-USD", "GC=F", "CL=F", "SI=F", "DX-Y.NYB", "EURUSD=X", "JPY=X"],
}

ALL_TICKERS = [t for group in WATCHLIST.values() for t in group]

TICKER_NAMES = {
    "^GSPC": "S&P 500", "^DJI": "DOW", "^IXIC": "NASDAQ", "^RUT": "Russell 2K",
    "^VIX": "VIX", "^FTSE": "FTSE 100", "^N225": "Nikkei 225", "^HSI": "Hang Seng",
    "SPY": "SPY", "QQQ": "QQQ", "IWM": "IWM", "GLD": "Gold ETF",
    "TLT": "20Y Treasury", "HYG": "High Yield", "EEM": "Emerging Mkts", "XLE": "Energy",
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "GOOGL": "Alphabet",
    "META": "Meta", "AMZN": "Amazon", "TSLA": "Tesla", "AMD": "AMD",
    "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum", "GC=F": "Gold", "CL=F": "Crude Oil",
    "SI=F": "Silver", "DX-Y.NYB": "USD Index", "EURUSD=X": "EUR/USD", "JPY=X": "USD/JPY",
}


@dataclass
class Quote:
    ticker: str
    name: str
    price: float
    change: float
    change_pct: float
    volume: Optional[int] = None
    market_cap: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    updated: datetime = field(default_factory=datetime.utcnow)

    @property
    def arrow(self) -> str:
        return "▲" if self.change >= 0 else "▼"

    @property
    def color(self) -> str:
        return "green" if self.change >= 0 else "red"


async def fetch_quotes(tickers: list[str]) -> dict[str, Quote]:
    loop = asyncio.get_event_loop()
    quotes = {}

    def _fetch():
        data = yf.download(
            tickers, period="2d", interval="1d",
            auto_adjust=True, progress=False, threads=True
        )
        results = {}
        for t in tickers:
            try:
                info = yf.Ticker(t).fast_info
                price = float(info.last_price or 0)
                prev  = float(info.previous_close or price)
                change = price - prev
                pct    = (change / prev * 100) if prev else 0
                results[t] = Quote(
                    ticker=t,
                    name=TICKER_NAMES.get(t, t),
                    price=price,
                    change=change,
                    change_pct=pct,
                    volume=int(info.three_month_average_volume or 0),
                    day_high=float(info.day_high or 0),
                    day_low=float(info.day_low or 0),
                )
            except Exception:
                pass
        return results

    try:
        quotes = await loop.run_in_executor(None, _fetch)
    except Exception:
        pass
    return quotes


async def fetch_ticker_prices(tickers: list[str]) -> dict[str, float]:
    """Lightweight price-only fetch for the top ticker bar."""
    loop = asyncio.get_event_loop()

    def _fetch():
        out = {}
        for t in tickers:
            try:
                info = yf.Ticker(t).fast_info
                out[t] = float(info.last_price or 0)
            except Exception:
                pass
        return out

    return await loop.run_in_executor(None, _fetch)
