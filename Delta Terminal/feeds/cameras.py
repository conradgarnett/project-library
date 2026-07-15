"""Public traffic & weather webcams — NOAA NDBC buoys + state DOT 511 systems.
All URLs serve actual JPEG/PNG images. DOT sources have CORS: *.
"""

import asyncio
import aiohttp
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CameraState:
    cameras: list = field(default_factory=list)
    updated: float = 0.0
    error: Optional[str] = None


# ── NOAA NDBC Ocean Buoy Cameras ────────────────────────────────────────────
# Image URL: https://www.ndbc.noaa.gov/buoycam.php?station=XXXXX
# All NDBC buoy cameras are 24/7 — ocean buoys transmit continuously
NDBC_BUOYS = [
    # Atlantic — East Coast
    ("44013", "Boston Harbor Approach",  "Boston, MA",         42.346,  -70.651, "atlantic"),
    ("44025", "New York Bight",          "New York, NY",       40.251,  -73.166, "atlantic"),
    ("44065", "New York Harbor",         "New York, NY",       40.369,  -73.703, "atlantic"),
    ("44008", "Nantucket SE",            "Nantucket, MA",      40.500,  -69.254, "atlantic"),
    ("44011", "Georges Bank",            "Cape Cod, MA",       41.088,  -66.546, "atlantic"),
    ("44014", "Virginia Beach",          "Virginia Beach, VA", 36.603,  -74.837, "atlantic"),
    ("41025", "Diamond Shoals",          "Cape Hatteras, NC",  35.026,  -75.380, "atlantic"),
    ("41048", "NW Atlantic",             "Atlantic Ocean",     31.890,  -69.708, "atlantic"),
    ("41049", "SE Atlantic",             "Atlantic Ocean",     27.505,  -62.271, "atlantic"),
    ("41047", "NE Atlantic",             "Atlantic Ocean",     27.514,  -71.495, "atlantic"),
    ("41001", "Gulf Stream",             "Atlantic Ocean",     34.930,  -72.659, "atlantic"),
    # Gulf of Mexico
    ("42001", "Central Gulf",            "Gulf of Mexico",     25.896,  -89.658, "gulf"),
    ("42036", "West Gulf",               "Gulf of Mexico",     28.500,  -84.517, "gulf"),
    # Pacific — West Coast
    ("46026", "San Francisco Bay Mouth", "San Francisco, CA",  37.759, -122.833, "pacific"),
    ("46025", "Santa Monica Basin",      "Los Angeles, CA",    33.765, -119.077, "pacific"),
    ("46053", "East Santa Barbara",      "Santa Barbara, CA",  34.248, -119.836, "pacific"),
    ("46054", "West Santa Barbara",      "Santa Barbara, CA",  34.274, -120.468, "pacific"),
    ("46028", "Cape San Martin",         "Big Sur, CA",        35.763, -121.893, "pacific"),
    ("46022", "Eel River",               "Eureka, CA",         40.716, -124.540, "pacific"),
    ("46027", "St Georges",              "Crescent City, CA",  41.840, -124.382, "pacific"),
    ("46086", "San Clemente Basin",      "San Diego, CA",      32.504, -118.029, "pacific"),
    ("46002", "Oregon Offshore",         "Portland, OR",       42.560, -130.523, "pacific"),
    ("46005", "Washington Offshore",     "Seattle, WA",        46.147, -131.077, "pacific"),
    ("46059", "Northern Pacific",        "Pacific Ocean",      38.054, -129.975, "pacific"),
    ("46011", "Santa Maria Basin",       "Santa Maria, CA",    34.868, -120.860, "pacific"),
    # Hawaii
    ("51001", "Hawaii NW",               "Pacific Ocean",      23.445, -162.279, "hawaii"),
    ("51002", "Hawaii South",            "Pacific Ocean",      17.094, -157.808, "hawaii"),
    ("51003", "Hawaii West",             "Pacific Ocean",      19.194, -160.741, "hawaii"),
    ("51004", "Hawaii SE",               "Pacific Ocean",      17.525, -152.382, "hawaii"),
]


def _ndbc_entry(station, name, city, lat, lon, category):
    return {
        "id": f"ndbc_{station}",
        "name": f"Buoy {station} — {name}",
        "city": city,
        "category": category,
        "lat": lat,
        "lon": lon,
        "url": f"https://www.ndbc.noaa.gov/buoycam.php?station={station}",
        "proxy": True,
    }


STATIC_CAMERAS = [_ndbc_entry(*s) for s in NDBC_BUOYS]


_state = CameraState(
    cameras=[dict(c, reachable=True) for c in STATIC_CAMERAS],
    updated=0.0,
)


def get_cameras():
    return _state


async def run_poller(interval: int = 600):
    """Probe each camera URL every 10 minutes and mark reachable/dead."""
    global _state

    async with aiohttp.ClientSession(headers={"User-Agent": "OpenBloomberg/1.0"}) as session:
        while True:
            live = []
            for cam in STATIC_CAMERAS:
                try:
                    async with session.head(
                        cam["url"],
                        timeout=aiohttp.ClientTimeout(total=6),
                        allow_redirects=True,
                    ) as r:
                        live.append(dict(cam, reachable=(r.status == 200)))
                except Exception:
                    live.append(dict(cam, reachable=False))

            _state.cameras = live
            _state.updated = time.time()
            await asyncio.sleep(interval)
