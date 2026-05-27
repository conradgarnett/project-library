"""
Satellite and space object tracking.
Sources (no API key required):
  - wheretheiss.at  — ISS real-time position
  - CelesTrak       — TLE catalog (active satellites, debris, stations)
  - n2yo.com        — supplementary passes (public)
"""

import asyncio
import time
import math
import aiohttp
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

ISS_API   = "https://api.wheretheiss.at/v1/satellites/25544"
TIANGONG_API = "https://api.wheretheiss.at/v1/satellites/48274"

CELESTRAK_GROUPS = {
    "stations":  "https://celestrak.org/SOCRATES/query.php?CATALOG=stations&FORMAT=json",
    "active":    "https://celestrak.org/SOCRATES/query.php?CATALOG=active&FORMAT=json",
    "starlink":  "https://celestrak.org/SOCRATES/query.php?CATALOG=starlink&FORMAT=json",
}

# CelesTrak CSV catalog
CELESTRAK_SAT_CAT = "https://celestrak.org/pub/TLE/catalog.txt"
CELESTRAK_ACTIVE  = "https://celestrak.org/SOCRATES/query.php?CATALOG=active&FORMAT=json"

# TLE sources
CELESTRAK_TLE = {
    "Stations":   "https://celestrak.org/SOCRATES/query.php?CATALOG=stations",
    "Starlink":   "https://celestrak.org/SOCRATES/query.php?CATALOG=starlink",
    "OneWeb":     "https://celestrak.org/SOCRATES/query.php?CATALOG=oneweb",
    "Active":     "https://celestrak.org/SOCRATES/query.php?CATALOG=active",
    "Debris":     "https://celestrak.org/SOCRATES/query.php?CATALOG=1999-025",
}

CELESTRAK_TLE_URLS = {
    "Stations": "https://celestrak.org/SOCRATES/query.php?CATALOG=stations",
    "Active":   "https://celestrak.org/pub/TLE/active.txt",
    "Starlink": "https://celestrak.org/pub/TLE/starlink.txt",
    "Visual":   "https://celestrak.org/pub/TLE/visual.txt",
    "ISS":      "https://celestrak.org/pub/TLE/stations.txt",
}


@dataclass
class SpaceStation:
    name: str
    norad_id: int
    lat: float
    lon: float
    altitude_km: float
    velocity_kms: float
    visibility: str = ""
    updated: float = field(default_factory=time.time)

    @property
    def altitude_mi(self) -> float:
        return self.altitude_km * 0.621371

    @property
    def ground_track(self) -> str:
        lat_str = f"{abs(self.lat):.2f}°{'N' if self.lat >= 0 else 'S'}"
        lon_str = f"{abs(self.lon):.2f}°{'E' if self.lon >= 0 else 'W'}"
        return f"{lat_str} {lon_str}"


@dataclass
class TLEObject:
    name: str
    norad_id: str
    intl_designator: str
    epoch: str
    period_min: float
    inclination: float
    apogee_km: float
    perigee_km: float
    eccentricity: float

    @property
    def orbit_type(self) -> str:
        avg = (self.apogee_km + self.perigee_km) / 2
        if avg < 2000:
            return "LEO"
        elif avg < 35000:
            return "MEO"
        elif abs(avg - 35786) < 1000:
            return "GEO"
        else:
            return "HEO"


@dataclass
class SpaceState:
    iss: Optional[SpaceStation] = None
    tiangong: Optional[SpaceStation] = None
    active_count: int = 0
    starlink_count: int = 0
    debris_count: int = 0
    notable: list[TLEObject] = field(default_factory=list)
    updated: float = field(default_factory=time.time)
    error: Optional[str] = None

    # Catalog stats
    total_objects: int = 0
    active_sats: int = 0


_state = SpaceState()


def get_space() -> SpaceState:
    return _state


async def _fetch_station(session: aiohttp.ClientSession, url: str, name: str, norad: int) -> Optional[SpaceStation]:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return None
            d = await r.json()
            return SpaceStation(
                name=name,
                norad_id=norad,
                lat=d["latitude"],
                lon=d["longitude"],
                altitude_km=d["altitude"],
                velocity_kms=d["velocity"] / 3600,
                visibility=d.get("visibility", ""),
            )
    except Exception:
        return None


async def _fetch_tle_catalog(session: aiohttp.ClientSession, url: str) -> list[TLEObject]:
    """Parse CelesTrak 3-line TLE format."""
    objects = []
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200:
                return objects
            text = await r.text()
            lines = [l.strip() for l in text.splitlines() if l.strip()]
            i = 0
            while i < len(lines) - 2:
                name = lines[i]
                l1   = lines[i + 1]
                l2   = lines[i + 2]
                if l1.startswith("1 ") and l2.startswith("2 ") and len(l1) >= 69 and len(l2) >= 69:
                    try:
                        norad = l1[2:7].strip()
                        intl  = l1[9:17].strip()
                        epoch = l1[18:32].strip()
                        inc   = float(l2[8:16].strip())
                        ecc   = float("0." + l2[26:33].strip())
                        mm    = float(l2[52:63].strip())
                        period = 1440.0 / mm
                        # Approximate apogee/perigee from mean motion
                        a_km  = (331.25 * (period) ** (2/3))
                        ecc_v = float("0." + l2[26:33].strip())
                        apo   = a_km * (1 + ecc_v) - 6371
                        per   = a_km * (1 - ecc_v) - 6371
                        objects.append(TLEObject(
                            name=name,
                            norad_id=norad,
                            intl_designator=intl,
                            epoch=epoch,
                            period_min=period,
                            inclination=inc,
                            apogee_km=apo,
                            perigee_km=per,
                            eccentricity=ecc_v,
                        ))
                    except Exception:
                        pass
                    i += 3
                else:
                    i += 1
    except Exception:
        pass
    return objects


async def run_poller(interval: int = 60):
    global _state
    async with aiohttp.ClientSession(headers={"User-Agent": "OpenBloomberg/1.0"}) as session:
        while True:
            iss = await _fetch_station(session, ISS_API, "ISS", 25544)
            tg  = await _fetch_station(session, TIANGONG_API, "Tiangong", 48274)

            # Fetch visual satellites TLE
            notable = await _fetch_tle_catalog(session, CELESTRAK_TLE_URLS["Visual"])
            starlink = await _fetch_tle_catalog(session, CELESTRAK_TLE_URLS["Starlink"])

            _state = SpaceState(
                iss=iss,
                tiangong=tg,
                active_count=len(notable),
                starlink_count=len(starlink),
                notable=notable[:50],
                updated=time.time(),
            )
            await asyncio.sleep(interval)
