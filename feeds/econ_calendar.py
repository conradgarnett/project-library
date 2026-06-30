"""Economic calendar — Finnhub economic events (US + major economies)."""

import asyncio
import aiohttp
import time
import os
from dataclasses import dataclass, field
from typing import Optional

FINNHUB_KEY = os.environ.get("FINNHUB_KEY", "")

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


async def _fetch(session: aiohttp.ClientSession) -> None:
    global _state
    url = f"https://finnhub.io/api/v1/calendar/economic?token={FINNHUB_KEY}"
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                _state.error = f"HTTP {r.status}"
                return
            data = await r.json()
            raw = data.get("economicCalendar", [])

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
    except Exception as ex:
        _state.error = str(ex)


async def run_poller(interval: int = 21600):
    if not FINNHUB_KEY:
        _state.error = "No FINNHUB_KEY"
        return
    async with aiohttp.ClientSession(
        headers={"User-Agent": "OpenBloombergTerminal/2.0"}
    ) as session:
        while True:
            await _fetch(session)
            await asyncio.sleep(interval)
