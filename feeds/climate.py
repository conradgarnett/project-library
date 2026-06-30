"""NOAA CDO Climate feed — annual & monthly summaries for major US stations.
Uses NOAA Climate Data Online (CDO) API — free with key.
"""

import asyncio
import aiohttp
import time
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

NOAA_CDO_KEY = os.environ.get("NOAA_CDO_KEY", "")
BASE = "https://www.ncdc.noaa.gov/cdo-web/api/v2"

# Major US stations: (ghcnd_id, city_name, lat, lon, state)
STATIONS = [
    ("USW00094789", "New York",    40.64, -73.78, "NY"),
    ("USW00094846", "Chicago",     41.98, -87.90, "IL"),
    ("USW00023174", "Los Angeles", 33.93, -118.39, "CA"),
    ("USW00012839", "Miami",       25.81, -80.28, "FL"),
    ("USW00024233", "Seattle",     47.45, -122.31, "WA"),
    ("USW00013874", "Atlanta",     33.64, -84.43, "GA"),
    ("USW00023062", "Denver",      39.86, -104.67, "CO"),
    ("USW00023183", "Phoenix",     33.44, -112.01, "AZ"),
    ("USW00014739", "Boston",      42.36, -71.01, "MA"),
    ("USW00026451", "Anchorage",   61.17, -150.02, "AK"),
]

# Data types for annual/monthly summaries
ANNUAL_TYPES  = "TAVG,TMAX,TMIN,PRCP,EMXT,EMNT"
MONTHLY_TYPES = "TAVG,TMAX,TMIN,PRCP"


@dataclass
class ClimateState:
    stations: list = field(default_factory=list)
    updated: float = 0.0
    error: Optional[str] = None


_state = ClimateState()


def get_climate():
    return _state


async def _fetch_json(session: aiohttp.ClientSession, url: str) -> dict:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=20),
                           headers={"token": NOAA_CDO_KEY}) as r:
        if r.status == 200:
            return await r.json()
        return {}


async def _fetch_station(session: aiohttp.ClientSession, station_id: str,
                          city: str, lat: float, lon: float, state: str) -> dict:
    today = date.today()
    # Annual: last 9 years (stay under 10-yr limit)
    year_start = date(today.year - 9, 1, 1)
    year_end   = date(today.year, 1, 1)
    annual_url = (f"{BASE}/data?datasetid=GSOY"
                  f"&stationid=GHCND:{station_id}"
                  f"&datatypeid={ANNUAL_TYPES}"
                  f"&startdate={year_start}&enddate={year_end}"
                  f"&limit=100&units=standard")

    # Monthly: last 24 months
    month_start = date(today.year - 2, today.month, 1)
    monthly_url = (f"{BASE}/data?datasetid=GSOM"
                   f"&stationid=GHCND:{station_id}"
                   f"&datatypeid={MONTHLY_TYPES}"
                   f"&startdate={month_start}&enddate={today}"
                   f"&limit=200&units=standard")

    try:
        annual_raw, monthly_raw = await asyncio.gather(
            _fetch_json(session, annual_url),
            _fetch_json(session, monthly_url),
        )
    except Exception as e:
        return {"id": station_id, "city": city, "state": state,
                "lat": lat, "lon": lon, "annual": [], "monthly": [], "error": str(e)}

    def pivot(records):
        by_date = {}
        for r in records.get("results", []):
            d = r["date"][:10][:7]  # YYYY-MM
            by_date.setdefault(d, {})["date"] = r["date"][:10]
            by_date[d][r["datatype"]] = r["value"]
        return sorted(by_date.values(), key=lambda x: x["date"])

    annual  = pivot(annual_raw)
    monthly = pivot(monthly_raw)

    # Compute linear trend for TAVG over annual data
    tavg_pts = [(i, r["TAVG"]) for i, r in enumerate(annual) if "TAVG" in r]
    trend = None
    if len(tavg_pts) >= 3:
        n = len(tavg_pts)
        xs = [p[0] for p in tavg_pts]
        ys = [p[1] for p in tavg_pts]
        mx, my = sum(xs)/n, sum(ys)/n
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = sum((x - mx)**2 for x in xs)
        trend = round(num / den, 3) if den else None  # °F per year

    latest_annual  = annual[-1]  if annual  else {}
    latest_monthly = monthly[-1] if monthly else {}

    return {
        "id":    station_id,
        "city":  city,
        "state": state,
        "lat":   lat,
        "lon":   lon,
        "annual":  annual,
        "monthly": monthly,
        "latest_annual":  latest_annual,
        "latest_monthly": latest_monthly,
        "trend_per_year": trend,
    }


async def _fetch_all(session: aiohttp.ClientSession) -> None:
    global _state
    # CDO rate limit: 5 req/sec. Each station makes 2 requests → process 2 stations/sec max.
    stations = []
    for sid, city, lat, lon, st in STATIONS:
        result = await _fetch_station(session, sid, city, lat, lon, st)
        stations.append(result)
        await asyncio.sleep(0.5)  # 2 stations/sec = 4 req/sec, under the 5/sec limit
    _state.stations = stations
    _state.updated = time.time()
    _state.error = None


async def run_poller(interval: int = 86400):
    if not NOAA_CDO_KEY:
        _state.error = "No NOAA_CDO_KEY"
        return
    async with aiohttp.ClientSession() as session:
        while True:
            await _fetch_all(session)
            await asyncio.sleep(interval)
