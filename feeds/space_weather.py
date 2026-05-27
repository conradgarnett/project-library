"""NOAA Space Weather Prediction Center — free, no key."""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class SpaceWeatherState:
    kp_index:     float  = 0.0
    kp_24h:       list   = field(default_factory=list)  # [{time, kp}, ...]
    solar_wind:   dict   = field(default_factory=dict)  # speed, density, bt
    x_ray_flux:   float  = 0.0
    alerts:       list   = field(default_factory=list)
    solar_regions:list   = field(default_factory=list)
    storm_level:  str    = "None"
    updated:      float  = 0.0
    error:        Optional[str] = None

_state = SpaceWeatherState()

def get_space_weather():
    return _state

STORM_LEVELS = {0:"None",1:"G1 Minor",2:"G2 Moderate",3:"G3 Strong",4:"G4 Severe",5:"G5 Extreme"}

def _kp_to_storm(kp: float) -> str:
    if kp >= 9: return STORM_LEVELS[5]
    if kp >= 8: return STORM_LEVELS[4]
    if kp >= 7: return STORM_LEVELS[3]
    if kp >= 6: return STORM_LEVELS[2]
    if kp >= 5: return STORM_LEVELS[1]
    return STORM_LEVELS[0]

def _kp_color(kp: float) -> str:
    if kp >= 7: return "#ff4466"
    if kp >= 5: return "#ff8800"
    if kp >= 4: return "#ffaa00"
    if kp >= 2: return "#00d4aa"
    return "#446688"

async def run_poller(interval: int = 300):
    global _state
    BASE = "https://services.swpc.noaa.gov"
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                # Kp index (1-minute)
                try:
                    async with session.get(
                        f"{BASE}/json/planetary_k_index_1m.json",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as r:
                        if r.status == 200:
                            data = await r.json()
                            kp_data = [
                                {"time": row[0][:16], "kp": float(row[1])}
                                for row in data[-24*60:]  # last 24h worth
                                if row[1] is not None
                            ]
                            _state.kp_24h = kp_data[-144:]  # last 2h at 1min = 120 pts, use last 144
                            if kp_data:
                                _state.kp_index = kp_data[-1]["kp"]
                                _state.storm_level = _kp_to_storm(_state.kp_index)
                except Exception:
                    pass

                # Solar wind plasma
                try:
                    async with session.get(
                        f"{BASE}/products/solar-wind/plasma-7-day.json",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as r:
                        if r.status == 200:
                            data = await r.json()
                            rows = [row for row in data[1:] if row[1] and row[2]]
                            if rows:
                                latest = rows[-1]
                                _state.solar_wind = {
                                    "speed":   float(latest[2]) if latest[2] else 0,
                                    "density": float(latest[1]) if latest[1] else 0,
                                    "temp":    float(latest[3]) if latest[3] else 0,
                                }
                except Exception:
                    pass

                # Alerts
                try:
                    async with session.get(
                        f"{BASE}/products/alerts.json",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as r:
                        if r.status == 200:
                            data = await r.json()
                            _state.alerts = [
                                {
                                    "issue_time": a.get("issue_datetime","")[:16],
                                    "message":    a.get("message","")[:200],
                                    "type":       a.get("message","")[:30],
                                }
                                for a in data[:10]
                            ]
                except Exception:
                    pass

                # Solar regions
                try:
                    async with session.get(
                        f"{BASE}/json/solar_regions.json",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as r:
                        if r.status == 200:
                            data = await r.json()
                            _state.solar_regions = [
                                {
                                    "region":  row[0],
                                    "lat":     row[1],
                                    "lon":     row[2],
                                    "class":   row[3],
                                    "flare_class": row[5] if len(row)>5 else "",
                                }
                                for row in (data[1:] if isinstance(data,list) else [])[:15]
                            ]
                except Exception:
                    pass

            _state.updated = time.time()
            _state.error = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
