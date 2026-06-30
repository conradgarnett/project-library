"""
Ocean & Sea Ice monitor
Sources:
  - NSIDC Sea Ice Index v4 (Arctic + Antarctic) — NOAA/NSIDC, no key
    https://noaadata.apps.nsidc.org/NOAA/G02135/
"""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

ARCTIC_URL    = "https://noaadata.apps.nsidc.org/NOAA/G02135/north/daily/data/N_seaice_extent_daily_v4.0.csv"
ANTARCTIC_URL = "https://noaadata.apps.nsidc.org/NOAA/G02135/south/daily/data/S_seaice_extent_daily_v4.0.csv"

# 1981–2010 climatological medians (approx) by month for anomaly calc
ARCTIC_CLIM = {
    1: 14.50, 2: 15.64, 3: 15.64, 4: 14.62, 5: 12.68, 6: 10.17,
    7:  7.68, 8:  5.84, 9:  6.24, 10: 8.96, 11: 11.64, 12: 13.46,
}
ANTARCTIC_CLIM = {
    1:  3.89, 2:  3.00, 3:  4.60, 4:  8.17, 5: 11.71, 6: 13.98,
    7: 15.51, 8: 16.62, 9: 17.57, 10: 16.12, 11: 11.89, 12:  6.29,
}


@dataclass
class PoleState:
    extent:    Optional[float] = None  # M km²
    date:      str             = ""
    anomaly:   Optional[float] = None  # vs climatological median
    trend:     list            = field(default_factory=list)  # last 60 days [{date, extent}]


@dataclass
class OceanState:
    arctic:    PoleState       = field(default_factory=PoleState)
    antarctic: PoleState       = field(default_factory=PoleState)
    updated:   float           = 0.0
    error:     Optional[str]   = None


_state = OceanState()


def get_ocean():
    return _state


def _parse_nsidc(csv_text: str, clim: dict) -> PoleState:
    pole = PoleState()
    rows = []
    for line in csv_text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.lower().startswith('year'):
            continue
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 4:
            continue
        try:
            year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            extent = float(parts[3])
            date_s = f"{year}-{month:02d}-{day:02d}"
            rows.append((date_s, month, extent))
        except (ValueError, IndexError):
            continue

    if not rows:
        return pole

    # Sort by date, take most recent as current
    rows.sort(key=lambda r: r[0])
    date_s, month, extent = rows[-1]
    pole.extent = round(extent, 3)
    pole.date   = date_s

    median = clim.get(month)
    if median:
        pole.anomaly = round(extent - median, 3)

    # trend: last 60 daily values
    pole.trend = [{"date": r[0], "extent": r[2]} for r in rows[-60:]]
    return pole


async def _fetch(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}")
        return await r.text()


async def run_poller(interval: int = 21600):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                arctic_txt, antarctic_txt = await asyncio.gather(
                    _fetch(session, ARCTIC_URL),
                    _fetch(session, ANTARCTIC_URL),
                )
            arctic    = _parse_nsidc(arctic_txt,    ARCTIC_CLIM)
            antarctic = _parse_nsidc(antarctic_txt, ANTARCTIC_CLIM)
            _state.arctic    = arctic
            _state.antarctic = antarctic
            _state.updated   = time.time()
            _state.error     = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
