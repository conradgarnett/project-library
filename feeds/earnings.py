"""Earnings calendar feed: Finnhub /calendar/earnings + yfinance fallback."""
import asyncio, aiohttp, time, os
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class EarningsState:
    upcoming: list = field(default_factory=list)  # next 2 weeks
    recent:   list = field(default_factory=list)  # past 1 week
    updated:  float = 0.0
    error:    Optional[str] = None

_state = EarningsState()

def get_earnings():
    return _state

# Equity-only symbols to use for yfinance fallback
_EQUITY_SYMBOLS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "META", "AMZN", "TSLA", "AMD",
    "AVGO", "ORCL", "NFLX", "CRM", "INTC", "QCOM", "TXN",
    "JPM", "BAC", "GS", "MS", "WFC",
    "JNJ", "UNH", "PFE", "MRK", "ABBV",
    "XOM", "CVX", "MCD", "KO", "WMT",
]

def _fmt_surprise(eps_est, eps_act):
    """Return surprise_pct or None."""
    try:
        e, a = float(eps_est), float(eps_act)
        if e != 0:
            return round((a - e) / abs(e) * 100, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        pass
    return None

def _make_record(symbol, dt_str, hour, eps_est, eps_act, rev_est, quarter, year):
    surprise = _fmt_surprise(eps_est, eps_act)
    return {
        "symbol":           symbol,
        "date":             dt_str,
        "hour":             hour or "—",
        "eps_estimate":     eps_est,
        "eps_actual":       eps_act,
        "revenue_estimate": rev_est,
        "surprise_pct":     surprise,
        "quarter":          quarter,
        "year":             year,
    }

async def _fetch_finnhub(session, from_date: str, to_date: str):
    key = os.environ.get("FINNHUB_KEY", "")
    if not key:
        return []
    url = (
        f"https://finnhub.io/api/v1/calendar/earnings"
        f"?from={from_date}&to={to_date}&token={key}"
    )
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                return []
            d = await r.json()
            records = []
            for item in d.get("earningsCalendar", []):
                sym = item.get("symbol", "")
                if not sym:
                    continue
                # Finnhub hour field: "bmo" / "amc" / ""
                raw_hour = (item.get("hour") or "").lower()
                hour = "BMO" if raw_hour == "bmo" else ("AMC" if raw_hour == "amc" else "—")
                records.append(_make_record(
                    symbol=sym,
                    dt_str=item.get("date", ""),
                    hour=hour,
                    eps_est=item.get("epsEstimate"),
                    eps_act=item.get("epsActual"),
                    rev_est=item.get("revenueEstimate"),
                    quarter=item.get("quarter"),
                    year=item.get("year"),
                ))
            return records
    except Exception:
        return []

def _fetch_yfinance_fallback(symbols, from_date: date, to_date: date):
    """Sync yfinance calls wrapped for asyncio.to_thread."""
    records = []
    try:
        import yfinance as yf
        for sym in symbols:
            try:
                cal = yf.Ticker(sym).calendar
                if cal is None:
                    continue
                # calendar is a dict with 'Earnings Date' key (list of Timestamps)
                earnings_dates = cal.get("Earnings Date", [])
                if not earnings_dates:
                    continue
                for ts in earnings_dates:
                    try:
                        dt = ts.date() if hasattr(ts, "date") else ts
                        if not (from_date <= dt <= to_date):
                            continue
                        records.append(_make_record(
                            symbol=sym,
                            dt_str=str(dt),
                            hour="—",
                            eps_est=cal.get("EPS Estimate"),
                            eps_act=None,
                            rev_est=cal.get("Revenue Estimate"),
                            quarter=None,
                            year=dt.year,
                        ))
                    except Exception:
                        continue
            except Exception:
                continue
    except ImportError:
        pass
    return records

async def run_poller(interval: int = 3600):
    global _state
    while True:
        try:
            today = date.today()
            past_start  = today - timedelta(days=7)
            future_end  = today + timedelta(days=14)

            from_str  = past_start.strftime("%Y-%m-%d")
            today_str = today.strftime("%Y-%m-%d")
            future_str = future_end.strftime("%Y-%m-%d")

            async with aiohttp.ClientSession() as session:
                # Fetch full window from Finnhub (past week + next 2 weeks)
                all_records = await _fetch_finnhub(session, from_str, future_str)

            # Fallback: use yfinance for upcoming if Finnhub returned nothing
            if not all_records:
                all_records = await asyncio.to_thread(
                    _fetch_yfinance_fallback, _EQUITY_SYMBOLS, past_start, future_end
                )

            # Split into upcoming (today onward) and recent (past week, with actuals)
            upcoming = sorted(
                [r for r in all_records if r["date"] >= today_str],
                key=lambda r: r["date"],
            )
            recent = sorted(
                [r for r in all_records if r["date"] < today_str],
                key=lambda r: r["date"],
                reverse=True,
            )

            _state.upcoming = upcoming
            _state.recent   = recent
            _state.updated  = time.time()
            _state.error    = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
