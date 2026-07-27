"""Economic calendar — Finnhub economic events (premium endpoint; falls back
to the FRED release calendar, which works with the free FRED_API_KEY)."""

import asyncio
import aiohttp
import time
import os
from datetime import date, timedelta
from dataclasses import dataclass, field
from typing import Optional

FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")
FRED_KEY    = os.environ.get("FRED_API_KEY", "")

# Countries to include (ISO-2 codes)
INCLUDE_COUNTRIES = {"US", "EU", "GB", "JP", "CN", "CA", "AU", "DE", "FR"}
INCLUDE_IMPACT = {"high", "medium"}

# Events that are always shown regardless of country if US-relevant
HIGH_VALUE_KEYWORDS = {
    "Fed", "FOMC", "CPI", "PCE", "NFP", "GDP", "Unemployment", "Payrolls",
    "Interest Rate", "Fed Funds", "PPI", "Retail Sales", "Housing", "ISM",
    "Consumer", "Inflation", "Jobs", "Nonfarm",
}


@dataclass
class EconCalState:
    events: list = field(default_factory=list)   # all filtered events sorted by time
    updated: float = 0.0
    error: Optional[str] = None


_state = EconCalState()


def get_econ_calendar():
    return _state


def _is_relevant(event: dict) -> bool:
    country = event.get("country", "")
    impact = event.get("impact", "low")
    name = event.get("event", "")

    if country in INCLUDE_COUNTRIES and impact in INCLUDE_IMPACT:
        return True
    # Always include Fed/FOMC regardless of impact label
    if country == "US" and any(kw.lower() in name.lower() for kw in HIGH_VALUE_KEYWORDS):
        return True
    return False


def _surprise(event: dict) -> Optional[float]:
    actual = event.get("actual")
    estimate = event.get("estimate")
    if actual is not None and estimate is not None and estimate != 0:
        return round(((actual - estimate) / abs(estimate)) * 100, 1)
    return None


# FRED release names worth showing, mapped to an impact label.
# (The full FRED calendar has ~400 releases in any 2-week window.)
_FRED_RELEASE_IMPACT = {
    "Employment Situation":                          "high",
    "Consumer Price Index":                          "high",
    "Producer Price Index":                          "high",
    "Personal Income and Outlays":                   "high",   # PCE
    "Gross Domestic Product":                        "high",
    "FOMC Press Release":                            "high",
    "Advance Monthly Sales for Retail and Food Services": "high",
    "Unemployment Insurance Weekly Claims Report":   "medium",
    "Consumer Sentiment":                            "medium",
    "Industrial Production and Capacity Utilization":"medium",
    "New Residential Construction":                  "medium",  # housing starts
    "New Residential Sales":                         "medium",
    "Existing Home Sales":                           "medium",
    "Durable Goods":                                 "medium",
    "Manufacturers' Shipments, Inventories, and Orders": "medium",
    "Job Openings and Labor Turnover Survey":        "medium",
    "H.15 Selected Interest Rates":                  "low",
}


async def _fetch_fred_releases(session: aiohttp.ClientSession) -> Optional[list]:
    """Upcoming US data releases from the FRED release calendar (free key)."""
    if not FRED_KEY:
        return None
    today = date.today()
    url = (
        "https://api.stlouisfed.org/fred/releases/dates"
        f"?api_key={FRED_KEY}&file_type=json"
        f"&realtime_start={today}&realtime_end={today + timedelta(days=14)}"
        "&include_release_dates_with_no_data=true&sort_order=asc&limit=1000"
    )
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=45)) as r:
        if r.status != 200:
            return None
        data = await r.json()
    events, seen = [], set()
    for rd in data.get("release_dates", []):
        name = rd.get("release_name", "")
        impact = next((imp for key, imp in _FRED_RELEASE_IMPACT.items()
                       if key.lower() in name.lower()), None)
        if not impact:
            continue
        key = (name, rd.get("date", ""))
        if key in seen:
            continue
        seen.add(key)
        events.append({
            "event":    name,
            "country":  "US",
            "impact":   impact,
            "time":     rd.get("date", ""),
            "actual":   None,
            "estimate": None,
            "prev":     None,
            "unit":     "",
            "surprise": None,
        })
    events.sort(key=lambda e: e["time"])
    return events


async def _fetch(session: aiohttp.ClientSession) -> None:
    """Try Finnhub; on any failure (it's a premium endpoint — 403 on free
    keys) fall back to the FRED release calendar."""
    global _state
    url = f"https://finnhub.io/api/v1/calendar/economic?token={FINNHUB_KEY}"
    raw = None
    finnhub_fail = None
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                raw = (await r.json()).get("economicCalendar", [])
            else:
                finnhub_fail = f"HTTP {r.status}"
    except Exception as ex:
        finnhub_fail = str(ex) or type(ex).__name__

    if raw is None:
        try:
            events = await _fetch_fred_releases(session)
        except Exception as ex:
            events = None
            finnhub_fail += f"; FRED fallback: {str(ex) or type(ex).__name__}"
        if events is not None:
            _state.events  = events
            _state.updated = time.time()
            _state.error   = None
        else:
            _state.error = f"Finnhub {finnhub_fail}"
        return

    events = []
    for e in raw:
        if not _is_relevant(e):
            continue
        events.append({
            "event":    e.get("event", ""),
            "country":  e.get("country", ""),
            "impact":   e.get("impact", "low"),
            "time":     e.get("time", ""),
            "actual":   e.get("actual"),
            "estimate": e.get("estimate"),
            "prev":     e.get("prev"),
            "unit":     e.get("unit", ""),
            "surprise": _surprise(e),
        })
    events.sort(key=lambda e: e["time"])
    _state.events = events
    _state.updated = time.time()
    _state.error = None


async def run_poller(interval: int = 21600):
    if not FINNHUB_KEY and not FRED_KEY:
        _state.error = "No FINNHUB_KEY or FRED_API_KEY"
        return
    async with aiohttp.ClientSession(
        headers={"User-Agent": "OpenBloombergTerminal/2.0"}
    ) as session:
        while True:
            if FINNHUB_KEY:
                await _fetch(session)
            else:
                try:
                    events = await _fetch_fred_releases(session)
                    if events is not None:
                        _state.events  = events
                        _state.updated = time.time()
                        _state.error   = None
                except Exception as ex:
                    _state.error = str(ex) or type(ex).__name__
            # Retry quickly while empty (e.g. timeout during startup rush)
            # instead of leaving the panel blank for the full 6h interval
            await asyncio.sleep(120 if not _state.events else interval)
