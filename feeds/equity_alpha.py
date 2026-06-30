"""Equity fundamentals via yfinance — no API key, no rate limit.
Fetches company overview for a curated watchlist once per day.
Falls back to Alpha Vantage if ALPHA_VANTAGE_KEY is set (kept for data quality comparison).
"""
import asyncio, os, time
from dataclasses import dataclass, field
from typing import Optional

WATCHLIST = [
    # Mega-cap tech
    "AAPL","MSFT","NVDA","GOOGL","META","AMZN","TSLA","AMD","AVGO","ORCL",
    "CRM","ADBE","INTC","QCOM","NFLX","UBER","ABNB","SNAP","PINS","RBLX",
    # Finance
    "JPM","GS","BAC","MS","V","MA","BRK-B","AXP","BLK","SCHW",
    # Healthcare
    "UNH","LLY","JNJ","PFE","MRK","ABBV","BMY","AMGN","GILD","CVS",
    # Energy & industrials
    "XOM","CVX","COP","NEE","GE","CAT","BA","LMT","RTX","HON",
    # Consumer
    "COST","WMT","HD","TGT","NKE","MCD","SBUX","DIS","CMCSA","T",
    # ETFs
    "SPY","QQQ","IWM","TLT","HYG","GLD","XLK","XLE","XLF","XLV",
]


@dataclass
class EquityFundamentals:
    fundamentals: dict = field(default_factory=dict)  # symbol → overview dict
    updated: float = 0.0
    error: Optional[str] = None


_state = EquityFundamentals()


def get_equity():
    return _state


def _yf_fetch_one(symbol: str) -> Optional[dict]:
    """Fetch fundamentals for one symbol via yfinance."""
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).info or {}
        if not info.get("regularMarketPrice") and not info.get("currentPrice") and not info.get("navPrice"):
            return None
        def _f(key):
            v = info.get(key)
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None
        return {
            "symbol":         symbol,
            "name":           info.get("longName") or info.get("shortName") or symbol,
            "sector":         info.get("sector", ""),
            "industry":       info.get("industry", ""),
            "exchange":       info.get("exchange", ""),
            "market_cap":     _f("marketCap"),
            "pe_ratio":       _f("trailingPE"),
            "forward_pe":     _f("forwardPE"),
            "eps":            _f("trailingEps"),
            "dividend_yield": _f("dividendYield"),
            "profit_margin":  _f("profitMargins"),
            "revenue_ttm":    _f("totalRevenue"),
            "gross_profit":   _f("grossProfits"),
            "week_52_high":   _f("fiftyTwoWeekHigh"),
            "week_52_low":    _f("fiftyTwoWeekLow"),
            "beta":           _f("beta"),
            "price_to_book":  _f("priceToBook"),
            "ev_to_ebitda":   _f("enterpriseToEbitda"),
            "shares_out":     _f("sharesOutstanding"),
            "analyst_target": _f("targetMeanPrice"),
            "ex_div_date":    info.get("exDividendDate", ""),
            "description":    (info.get("longBusinessSummary") or "")[:300],
            "employees":      info.get("fullTimeEmployees"),
            "revenue":        _f("totalRevenue"),
        }
    except Exception:
        return None


async def run_poller(interval: int = 86400):
    """Fetch fundamentals for the full watchlist once per day via yfinance."""
    global _state
    from feeds.yf_throttle import run as yf_run
    while True:
        try:
            results = {}
            for symbol in WATCHLIST:
                result = await yf_run(_yf_fetch_one, symbol)
                if result:
                    results[symbol] = result
            if results:
                _state.fundamentals = results
                _state.updated = time.time()
                _state.error = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
