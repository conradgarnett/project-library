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

# tle.ivanstanojevic.me — free TLE API, no key required
TLE_API = "https://tle.ivanstanojevic.me/api/tle"
NORAD_TIANGONG = 48274   # CSS (Tianhe core module)
NORAD_ISS      = 25544

# Notable NORAD IDs for the "visual" satellites list
NOTABLE_NORAD = [
    25544,   # ISS
    48274,   # Tiangong CSS
    43013,   # NOAA-20
    33591,   # NOAA-19
    28654,   # NOAA-18
    25994,   # Terra
    27424,   # Aqua
    38771,   # Suomi NPP
    49260,   # Landsat 9
    39634,   # Landsat 8
]


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
    crew: list = field(default_factory=list)
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


async def _fetch_tle_catalog_from_lines(name: str, line1: str, line2: str) -> Optional[TLEObject]:
    """Parse a single TLE into a TLEObject."""
    try:
        import math
        norad = line1[2:7].strip()
        intl  = line1[9:17].strip()
        epoch = line1[18:32].strip()
        inc   = float(line2[8:16].strip())
        ecc   = float("0." + line2[26:33].strip())
        mm    = float(line2[52:63].strip())
        period = 1440.0 / mm
        a_km  = 331.25 * (period ** (2/3))
        apo   = a_km * (1 + ecc) - 6371
        per   = a_km * (1 - ecc) - 6371
        return TLEObject(
            name=name, norad_id=norad, intl_designator=intl,
            epoch=epoch, period_min=period, inclination=inc,
            apogee_km=apo, perigee_km=per, eccentricity=ecc,
        )
    except Exception:
        return None


async def _fetch_tle(session: aiohttp.ClientSession, norad_id: int) -> Optional[tuple]:
    """Fetch TLE for a given NORAD ID from tle.ivanstanojevic.me."""
    try:
        async with session.get(
            f"{TLE_API}/{norad_id}",
            timeout=aiohttp.ClientTimeout(total=8),
        ) as r:
            if r.status != 200:
                return None
            d = await r.json()
            return (d.get("name", ""), d.get("line1", ""), d.get("line2", ""))
    except Exception:
        return None


def _tle_to_position(name: str, norad: int, line1: str, line2: str) -> Optional[SpaceStation]:
    """Propagate a TLE to current position using sgp4."""
    try:
        from sgp4.api import Satrec, jday
        import math
        from datetime import datetime, timezone

        sat = Satrec.twoline2rv(line1, line2)
        now = datetime.now(timezone.utc)
        jd, fr = jday(now.year, now.month, now.day, now.hour, now.minute, now.second + now.microsecond / 1e6)
        e, r, v = sat.sgp4(jd, fr)
        if e != 0:
            return None

        # ECI → geographic via GMST
        days_j2000 = jd + fr - 2451545.0
        gmst = math.radians((280.46061837 + 360.98564736629 * days_j2000) % 360)

        x, y, z = r
        lon_rad = math.atan2(y, x) - gmst
        lon = math.degrees(lon_rad) % 360
        if lon > 180:
            lon -= 360
        p = math.sqrt(x**2 + y**2)
        lat = math.degrees(math.atan2(z, p))
        alt = math.sqrt(x**2 + y**2 + z**2) - 6371.0

        vx, vy, vz = v
        speed = math.sqrt(vx**2 + vy**2 + vz**2)

        return SpaceStation(
            name=name,
            norad_id=norad,
            lat=round(lat, 6),
            lon=round(lon, 6),
            altitude_km=round(alt, 3),
            velocity_kms=round(speed, 4),
            visibility="",
        )
    except Exception:
        return None


async def _fetch_tle_count(session: aiohttp.ClientSession, search: str) -> int:
    """Get satellite count from TLE API search."""
    try:
        async with session.get(
            f"{TLE_API}/?search={search}&page-size=1",
            timeout=aiohttp.ClientTimeout(total=8),
        ) as r:
            if r.status != 200:
                return 0
            d = await r.json()
            return int(d.get("totalItems", 0))
    except Exception:
        return 0


async def run_poller(interval: int = 60):
    global _state
    async with aiohttp.ClientSession(headers={"User-Agent": "OpenBloomberg/1.0"}) as session:
        while True:
            # ISS real-time from wheretheiss.at
            iss = await _fetch_station(session, ISS_API, "ISS", NORAD_ISS)

            # Tiangong via TLE propagation
            tg_tle = await _fetch_tle(session, NORAD_TIANGONG)
            tg = None
            if tg_tle:
                tg = _tle_to_position(tg_tle[0], NORAD_TIANGONG, tg_tle[1], tg_tle[2])

            # Notable satellites via TLE propagation
            notable_tles = await asyncio.gather(
                *[_fetch_tle(session, nid) for nid in NOTABLE_NORAD],
                return_exceptions=True,
            )
            notable = []
            for tle in notable_tles:
                if isinstance(tle, tuple) and tle[0] and tle[1] and tle[2]:
                    obj = await _fetch_tle_catalog_from_lines(tle[0], tle[1], tle[2])
                    if obj:
                        notable.append(obj)

            # Starlink count from TLE API
            starlink_count = await _fetch_tle_count(session, "STARLINK")
            active_count   = await _fetch_tle_count(session, "")

            # Crew aboard space stations (open-notify.org, updates infrequently)
            crew = _state.crew
            try:
                async with session.get(
                    "http://api.open-notify.org/astros.json",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        crew = data.get("people", [])
            except Exception:
                pass

            _state = SpaceState(
                iss=iss,
                tiangong=tg,
                active_count=active_count,
                starlink_count=starlink_count,
                notable=notable,
                crew=crew,
                updated=time.time(),
            )
            await asyncio.sleep(interval)
