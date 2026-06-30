"""NASA FIRMS wildfire hotspots — free map key from firms.modaps.eosdis.nasa.gov."""
import asyncio, aiohttp, os, time
from dataclasses import dataclass, field
from typing import Optional

FIRMS_KEY = os.environ.get("FIRMS_MAP_KEY", "")   # free at https://firms.modaps.eosdis.nasa.gov/api/

@dataclass
class WildfireState:
    hotspots: list = field(default_factory=list)   # [{lat, lon, brightness, frp, acq_date, confidence}]
    count:    int  = 0
    updated:  float = 0.0
    error:    Optional[str] = None

_state = WildfireState()

def get_wildfires():
    return _state

async def run_poller(interval: int = 10800):   # 3h — FIRMS updates 3x/day
    global _state
    while True:
        if FIRMS_KEY:
            try:
                # Try VIIRS SNPP first (higher resolution), fall back to MODIS
                sources = [
                    ("VIIRS_SNPP_NRT", "bright_ti4"),
                    ("MODIS_NRT",       "brightness"),
                ]
                hotspots = []
                async with aiohttp.ClientSession() as session:
                    for product, bright_col in sources:
                        if hotspots:
                            break
                        url = (
                            f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
                            f"{FIRMS_KEY}/{product}/world/1"
                        )
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                            if r.status != 200:
                                continue
                            text = await r.text()
                            lines = text.strip().splitlines()
                            if len(lines) <= 1:
                                continue   # empty — try next source
                            headers = [h.strip() for h in lines[0].split(",")]
                            for line in lines[1:]:
                                parts = line.split(",")
                                if len(parts) < len(headers):
                                    continue
                                row = dict(zip(headers, parts))
                                try:
                                    conf = row.get("confidence", "").strip()
                                    if conf in ("l", ""):
                                        continue
                                    hotspots.append({
                                        "lat":        float(row.get("latitude", 0)),
                                        "lon":        float(row.get("longitude", 0)),
                                        "brightness": float(row.get(bright_col, 0) or 0),
                                        "frp":        float(row.get("frp", 0) or 0),
                                        "date":       row.get("acq_date", ""),
                                        "confidence": conf,
                                        "satellite":  row.get("satellite", ""),
                                    })
                                except Exception:
                                    continue
                _state.hotspots = hotspots
                _state.count    = len(hotspots)
                _state.updated  = time.time()
                _state.error    = None
            except Exception as e:
                _state.error = str(e)
        else:
            _state.error = "Set FIRMS_MAP_KEY (free at firms.modaps.eosdis.nasa.gov/api/)"
        await asyncio.sleep(interval)
