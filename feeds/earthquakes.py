"""Real-time earthquake data from USGS — no API key required."""

import asyncio
import time
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

USGS_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson"
USGS_DAY  = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"
USGS_SIG  = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson"

ALERT_COLORS = {
    "green":  "green",
    "yellow": "yellow",
    "orange": "dark_orange",
    "red":    "red",
}


@dataclass
class Earthquake:
    event_id: str
    magnitude: float
    mag_type: str
    place: str
    lat: float
    lon: float
    depth_km: float
    time_utc: datetime
    felt: int
    alert: Optional[str]
    tsunami: bool
    sig: int
    url: str
    updated: float = field(default_factory=time.time)

    @property
    def magnitude_str(self) -> str:
        return f"M{self.magnitude:.1f}"

    @property
    def severity_color(self) -> str:
        if self.magnitude >= 7.0:
            return "red"
        elif self.magnitude >= 6.0:
            return "dark_orange"
        elif self.magnitude >= 5.0:
            return "yellow"
        elif self.magnitude >= 4.0:
            return "cyan"
        else:
            return "dim"

    @property
    def time_ago(self) -> str:
        delta = datetime.now(timezone.utc) - self.time_utc
        secs = int(delta.total_seconds())
        if secs < 60:
            return f"{secs}s ago"
        elif secs < 3600:
            return f"{secs // 60}m ago"
        elif secs < 86400:
            return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"


@dataclass
class EarthquakeState:
    recent: list[Earthquake] = field(default_factory=list)
    significant: list[Earthquake] = field(default_factory=list)
    hourly_count: int = 0
    daily_count: int = 0
    largest_today: Optional[Earthquake] = None
    updated: float = field(default_factory=time.time)
    error: Optional[str] = None


_state = EarthquakeState()


def get_earthquakes() -> EarthquakeState:
    return _state


def _parse_features(features: list) -> list[Earthquake]:
    quakes = []
    for f in features:
        try:
            p = f["properties"]
            g = f["geometry"]["coordinates"]
            t = datetime.fromtimestamp(p["time"] / 1000, tz=timezone.utc)
            quakes.append(Earthquake(
                event_id=f["id"],
                magnitude=float(p.get("mag") or 0),
                mag_type=p.get("magType", ""),
                place=p.get("place", "Unknown location"),
                lat=g[1],
                lon=g[0],
                depth_km=g[2],
                time_utc=t,
                felt=int(p.get("felt") or 0),
                alert=p.get("alert"),
                tsunami=bool(p.get("tsunami")),
                sig=int(p.get("sig") or 0),
                url=p.get("url", ""),
            ))
        except Exception:
            pass
    return sorted(quakes, key=lambda q: q.time_utc, reverse=True)


async def run_poller(interval: int = 60):
    global _state
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.get(USGS_URL, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    hourly = _parse_features((await r.json())["features"]) if r.status == 200 else []

                async with session.get(USGS_DAY, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    daily = _parse_features((await r.json())["features"]) if r.status == 200 else []

                async with session.get(USGS_SIG, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    significant = _parse_features((await r.json())["features"]) if r.status == 200 else []

                largest = max(daily, key=lambda q: q.magnitude) if daily else None
                _state = EarthquakeState(
                    recent=hourly,
                    significant=significant[:20],
                    hourly_count=len(hourly),
                    daily_count=len(daily),
                    largest_today=largest,
                    updated=time.time(),
                )
            except Exception as e:
                _state.error = str(e)
                _state.updated = time.time()

            await asyncio.sleep(interval)
