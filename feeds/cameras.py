"""Public traffic & city webcams — no API key required.

Sources:
  - WSDOT (Washington State DOT) — free, no key, refreshes every 2 min
  - NOAA/NWS weather station cams — public
  - Curated city/landmark cams with direct public image URLs
"""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class CameraState:
    cameras: list = field(default_factory=list)
    updated: float = 0.0
    error:   Optional[str] = None

_state = CameraState()

def get_cameras():
    return _state

# Curated public cameras with direct image URLs (no key, no auth)
STATIC_CAMERAS = [
    # WSDOT (Washington State DOT) — public JPEG snapshots
    {"id":"wsdot_9701", "name":"I-5 NB at Seattle (S Horton St)",   "city":"Seattle, WA",    "category":"traffic", "lat":47.594, "lon":-122.324, "url":"https://images.wsdot.wa.gov/nw/009vc09701.jpg"},
    {"id":"wsdot_8411", "name":"I-5 at Tacoma (S 56th St)",          "city":"Tacoma, WA",     "category":"traffic", "lat":47.175, "lon":-122.449, "url":"https://images.wsdot.wa.gov/sw/005vc08411.jpg"},
    {"id":"wsdot_8103", "name":"SR-99 Tunnel North Portal",          "city":"Seattle, WA",    "category":"traffic", "lat":47.608, "lon":-122.341, "url":"https://images.wsdot.wa.gov/nw/099vc08103.jpg"},
    {"id":"wsdot_9339", "name":"I-90 at Mercer Island",              "city":"Mercer Island, WA","category":"traffic","lat":47.578,"lon":-122.220, "url":"https://images.wsdot.wa.gov/ms/090vc09339.jpg"},
    {"id":"wsdot_4077", "name":"US-2 at Stevens Pass Summit",        "city":"Stevens Pass, WA","category":"mountain","lat":47.744,"lon":-121.089, "url":"https://images.wsdot.wa.gov/nc/002vc04077.jpg"},
    {"id":"wsdot_5175", "name":"US-2 at Snoqualmie Pass",            "city":"Snoqualmie Pass, WA","category":"mountain","lat":47.425,"lon":-121.411, "url":"https://images.wsdot.wa.gov/ms/090vc05175.jpg"},
    # NOAA weather station cameras (public)
    {"id":"noaa_hilo",  "name":"NOAA — Hilo, Hawaii",                "city":"Hilo, HI",       "category":"weather", "lat":19.72, "lon":-155.07, "url":"https://www.weather.gov/images/hfo/webcam/hilo_latest.jpg"},
    {"id":"noaa_juneau","name":"NOAA — Juneau, Alaska",              "city":"Juneau, AK",     "category":"weather", "lat":58.30, "lon":-134.42, "url":"https://www.weather.gov/images/pajk/webcam/juneau_latest.jpg"},
    # USGS volcano cams (HVO — public)
    {"id":"usgs_kil1",  "name":"USGS — Kilauea Summit (HVO)",        "city":"Hawaii Volcanoes NP","category":"science","lat":19.41,"lon":-155.29, "url":"https://volcanoes.usgs.gov/vsc/captures/kilauea/2011HVO_overview.jpg"},
    # FAA / airport approach cams (some airports publish public snapshots)
    {"id":"pdx_appr",   "name":"PDX Airport Approach (Troutdale)",   "city":"Portland, OR",   "category":"aviation","lat":45.549,"lon":-122.401, "url":"https://weathercams.faa.gov/camera/TROUTDALE/latest.jpg"},
    {"id":"sea_appr",   "name":"SEA Airport Approach (Renton)",      "city":"Seattle, WA",    "category":"aviation","lat":47.490,"lon":-122.218, "url":"https://weathercams.faa.gov/camera/RENTON/latest.jpg"},
    {"id":"anc_appr",   "name":"ANC Airport Approach",               "city":"Anchorage, AK",  "category":"aviation","lat":61.174,"lon":-149.996, "url":"https://weathercams.faa.gov/camera/ANCHORAGE_INT/latest.jpg"},
    {"id":"den_appr",   "name":"DEN Airport Approach (Watkins)",     "city":"Denver, CO",     "category":"aviation","lat":39.760,"lon":-104.572, "url":"https://weathercams.faa.gov/camera/WATKINS/latest.jpg"},
    # COTRIP (Colorado DOT) — public, no key
    {"id":"cotrip_i70", "name":"I-70 at Vail Pass Summit",           "city":"Vail Pass, CO",  "category":"traffic", "lat":39.543,"lon":-106.228, "url":"https://cotrip.org/cameras/I-070D/I-070D-262.00BVAI.jpg"},
    {"id":"cotrip_i70e","name":"I-70 Eisenhower Tunnel East Portal",  "city":"Dillon, CO",     "category":"traffic", "lat":39.677,"lon":-105.906, "url":"https://cotrip.org/cameras/I-070D/I-070D-216.40ETUN.jpg"},
]

async def run_poller(interval: int = 300):
    global _state
    while True:
        try:
            # Verify which cameras are reachable (HEAD check)
            live = []
            async with aiohttp.ClientSession() as session:
                for cam in STATIC_CAMERAS:
                    try:
                        async with session.head(cam["url"], timeout=aiohttp.ClientTimeout(total=5), allow_redirects=True) as r:
                            cam_copy = dict(cam)
                            cam_copy["reachable"] = (r.status == 200)
                            live.append(cam_copy)
                    except Exception:
                        cam_copy = dict(cam)
                        cam_copy["reachable"] = False
                        live.append(cam_copy)
            _state.cameras = live
            _state.updated = time.time()
            _state.error   = None
        except Exception as e:
            _state.error = str(e)
            if not _state.cameras:
                _state.cameras = [dict(c, reachable=True) for c in STATIC_CAMERAS]
        await asyncio.sleep(interval)
