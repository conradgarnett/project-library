"""Live aircraft positions via OpenSky Network — anonymous, no API key required."""

import asyncio
import time
import aiohttp
from dataclasses import dataclass, field
from typing import Optional

OPENSKY_URL = "https://opensky-network.org/api/states/all"

# Approximate lat/lon bounding box — None = worldwide
BBOX: Optional[tuple] = None  # (lat_min, lat_max, lon_min, lon_max)

CATEGORIES = {
    0: "Unknown", 1: "No info", 2: "Light (<15500 lbs)",
    3: "Small (15500-75000 lbs)", 4: "Large (75000-300000 lbs)",
    5: "High vortex", 6: "Heavy (>300000 lbs)", 7: "High perf",
    8: "Rotorcraft", 9: "Glider", 10: "Lighter-than-air",
    11: "Skydiver", 12: "Ultralight", 13: "Reserved",
    14: "UAV", 15: "Space/Trans-atmospheric", 16: "Surface emergency",
    17: "Surface service", 18: "Point obstacle", 19: "Cluster obstacle",
    20: "Line obstacle",
}

COUNTRIES = {
    "a": "USA", "c": "Canada", "e": "Germany/Spain/Portugal",
    "4": "Finland", "7": "Russia",
}


@dataclass
class Aircraft:
    icao24: str
    callsign: str
    origin_country: str
    longitude: Optional[float]
    latitude: Optional[float]
    altitude_m: Optional[float]
    on_ground: bool
    velocity_ms: Optional[float]
    heading: Optional[float]
    vertical_rate: Optional[float]
    category: int = 0
    last_contact: float = 0.0

    @property
    def altitude_ft(self) -> Optional[float]:
        return self.altitude_m * 3.28084 if self.altitude_m else None

    @property
    def speed_kts(self) -> Optional[float]:
        return self.velocity_ms * 1.94384 if self.velocity_ms else None

    @property
    def heading_arrow(self) -> str:
        if self.heading is None:
            return "·"
        arrows = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]
        idx = round(self.heading / 45) % 8
        return arrows[idx]

    @property
    def fl(self) -> str:
        if self.altitude_ft is None:
            return "GND" if self.on_ground else "---"
        return f"FL{int(self.altitude_ft / 100):03d}"


@dataclass
class AircraftState:
    aircraft: list[Aircraft] = field(default_factory=list)
    total: int = 0
    airborne: int = 0
    updated: float = field(default_factory=time.time)
    error: Optional[str] = None


_state = AircraftState()


def get_aircraft() -> AircraftState:
    return _state


def _parse_states(data: dict) -> list[Aircraft]:
    planes = []
    for s in (data.get("states") or []):
        if len(s) < 17:
            continue
        planes.append(Aircraft(
            icao24=s[0] or "",
            callsign=(s[1] or "").strip(),
            origin_country=s[2] or "",
            longitude=s[5],
            latitude=s[6],
            altitude_m=s[7],
            on_ground=bool(s[8]),
            velocity_ms=s[9],
            heading=s[10],
            vertical_rate=s[11],
            category=s[17] if len(s) > 17 and s[17] else 0,
            last_contact=s[4] or 0,
        ))
    return planes


async def fetch_aircraft(session: aiohttp.ClientSession) -> AircraftState:
    global _state
    params = {}
    if BBOX:
        params = {"lamin": BBOX[0], "lamax": BBOX[1], "lomin": BBOX[2], "lomax": BBOX[3]}
    try:
        async with session.get(OPENSKY_URL, params=params, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                data = await r.json()
                planes = _parse_states(data)
                _state = AircraftState(
                    aircraft=planes,
                    total=len(planes),
                    airborne=sum(1 for p in planes if not p.on_ground),
                    updated=time.time(),
                )
            elif r.status == 429:
                _state.error = "Rate limited — OpenSky (retry in 10s)"
            else:
                _state.error = f"HTTP {r.status}"
    except asyncio.TimeoutError:
        _state.error = "Timeout connecting to OpenSky"
    except Exception as e:
        _state.error = str(e)
    return _state


async def run_poller(interval: int = 15):
    async with aiohttp.ClientSession() as session:
        while True:
            await fetch_aircraft(session)
            await asyncio.sleep(interval)
