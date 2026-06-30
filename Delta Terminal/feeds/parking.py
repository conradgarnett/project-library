"""
Real-time parking occupancy from open city APIs. No key required.

Sources with actual occupancy (not just locations):
  - TfL (London) — Car parks + Cycle hire, free, no key
  - SFMTA (San Francisco) — Off-street garages, Socrata
  - Birmingham UK — NCP & council garages, open data
  - Leeds UK — city centre car parks, open data
  - Cologne (Köln) DE — Stadtwerke open data
  - Newcastle UK — city car parks, open data
  - Bristol UK — city car parks, open data
"""

import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ParkingLot:
    id:          str
    name:        str
    city:        str
    country:     str
    total:       int
    occupied:    Optional[int]
    free:        Optional[int]
    occ_pct:     Optional[float]
    lat:         Optional[float]
    lon:         Optional[float]
    type:        str = "car_park"    # car_park | garage | street

    @property
    def status(self):
        if self.occ_pct is None: return "Unknown"
        if self.occ_pct >= 95:   return "Full"
        if self.occ_pct >= 80:   return "Busy"
        if self.occ_pct >= 50:   return "Moderate"
        return "Available"

@dataclass
class ParkingState:
    lots:    list  = field(default_factory=list)
    by_city: dict  = field(default_factory=dict)
    summary: dict  = field(default_factory=dict)
    updated: float = 0.0
    error:   Optional[str] = None

_state = ParkingState()

def get_parking():
    return _state

def _pct(occ, total):
    if occ is None or not total: return None
    return round(occ / total * 100, 1)

# ── London — TfL Santander Cycle Hire (BikePoint) ────────────────────────────
async def _fetch_tfl(session):
    lots = []
    try:
        async with session.get(
            "https://api.tfl.gov.uk/BikePoint",
            timeout=aiohttp.ClientTimeout(total=15)
        ) as r:
            if r.status == 200:
                data = await r.json()
                for p in data:
                    props = {x["key"]: x["value"] for x in p.get("additionalProperties", [])}
                    total = int(props.get("NbDocks") or 0)
                    bikes = int(props.get("NbBikes") or 0)
                    free  = int(props.get("NbEmptyDocks") or 0)
                    if not total:
                        continue
                    occ = total - free
                    coords = p.get("additionalProperties", [])
                    lat = float(p.get("lat") or 0) or None
                    lon = float(p.get("lon") or 0) or None
                    lots.append(ParkingLot(
                        id=p.get("id", ""),
                        name=(p.get("commonName") or "London Cycle Dock")[:50],
                        city="London",
                        country="GB",
                        total=total,
                        occupied=occ,
                        free=free,
                        occ_pct=_pct(occ, total),
                        lat=lat, lon=lon,
                        type="bike_dock",
                    ))
    except Exception:
        pass
    return lots

# ── SFMTA San Francisco off-street garages ────────────────────────────────────
async def _fetch_sf(session):
    lots = []
    try:
        # SFMTA off-street parking facilities
        async with session.get(
            "https://data.sfgov.org/resource/uaqp-pepe.json?$limit=80",
            timeout=aiohttp.ClientTimeout(total=12)
        ) as r:
            if r.status == 200:
                data = await r.json()
                for row in data:
                    total = int(row.get("total_spaces", 0) or 0)
                    avail = int(row.get("available_spaces", row.get("ms_spaces_available", 0)) or 0)
                    if not total: continue
                    occ = total - avail
                    loc = row.get("location_1", {}) or {}
                    lat = float(loc.get("latitude", 0) or 0) or None
                    lon = float(loc.get("longitude", 0) or 0) or None
                    lots.append(ParkingLot(
                        id=row.get("facil_id", row.get("objectid", "")),
                        name=(row.get("name", row.get("facility_name", "Unknown")) or "Unknown")[:50],
                        city="San Francisco",
                        country="US",
                        total=total,
                        occupied=occ,
                        free=avail,
                        occ_pct=_pct(occ, total),
                        lat=lat, lon=lon,
                        type="garage",
                    ))
    except Exception:
        pass
    # fallback: SFMTA on-street sensor summary by neighborhood
    if not lots:
        try:
            async with session.get(
                "https://data.sfgov.org/resource/9ivs-nf5y.json?$limit=50",
                timeout=aiohttp.ClientTimeout(total=12)
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    for row in data:
                        total = int(row.get("spaces", row.get("supply", 0)) or 0)
                        if not total: continue
                        lots.append(ParkingLot(
                            id=row.get("id", row.get("objectid", "")),
                            name=(row.get("name", row.get("block_face", "")) or "SF Lot")[:50],
                            city="San Francisco",
                            country="US",
                            total=total,
                            occupied=None,
                            free=None,
                            occ_pct=None,
                            lat=None, lon=None,
                            type="street",
                        ))
        except Exception:
            pass
    return lots

# ── Bordeaux FR — real-time car parks ────────────────────────────────────────
async def _fetch_bordeaux(session):
    lots = []
    try:
        async with session.get(
            "https://opendata.bordeaux-metropole.fr/api/explore/v2.1/catalog/datasets/"
            "st_park_p/records?limit=50&where=connecte=1",
            timeout=aiohttp.ClientTimeout(total=12)
        ) as r:
            if r.status == 200:
                data = await r.json()
                for row in data.get("results", []):
                    total = int(row.get("total") or 0)
                    free  = int(row.get("libres") or 0)
                    if not total:
                        continue
                    occ = total - free
                    geo = row.get("geo_point_2d") or {}
                    lots.append(ParkingLot(
                        id=str(row.get("ident", row.get("gid", ""))),
                        name=(row.get("nom") or "Bordeaux Parking")[:50],
                        city="Bordeaux",
                        country="FR",
                        total=total,
                        occupied=occ,
                        free=free,
                        occ_pct=_pct(occ, total),
                        lat=geo.get("lat"),
                        lon=geo.get("lon"),
                    ))
    except Exception:
        pass
    return lots

# ── Cologne DE — ArcGIS open data ────────────────────────────────────────────
async def _fetch_cologne(session):
    lots = []
    try:
        url = (
            "https://geoportal.stadt-koeln.de/arcgis/rest/services/Parkhaus/MapServer/0/query"
            "?where=1%3D1&outFields=*&f=json&resultRecordCount=100"
        )
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status == 200:
                data = await r.json()
                for feat in data.get("features", []):
                    a = feat.get("attributes", {})
                    total = int(a.get("KAPAZITAET") or a.get("Kapazitaet") or 0)
                    free  = int(a.get("FREI") or a.get("Frei") or a.get("FREIE_PLAETZE") or 0)
                    if not total:
                        continue
                    occ = total - free
                    geo = feat.get("geometry", {}) or {}
                    lat = float(geo.get("y") or 0) or None
                    lon = float(geo.get("x") or 0) or None
                    lots.append(ParkingLot(
                        id=str(a.get("OBJECTID", a.get("FID", ""))),
                        name=(a.get("NAME") or a.get("BEZEICHNUNG") or "Köln Parkhaus")[:50],
                        city="Cologne",
                        country="DE",
                        total=total,
                        occupied=occ,
                        free=free,
                        occ_pct=_pct(occ, total),
                        lat=lat, lon=lon,
                    ))
    except Exception:
        pass
    return lots

# ── Paris FR — Vélib' Métropole bike share ────────────────────────────────────
async def _fetch_paris(session):
    lots = []
    try:
        async with session.get(
            "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/"
            "velib-disponibilite-en-temps-reel/records?limit=100",
            timeout=aiohttp.ClientTimeout(total=12)
        ) as r:
            if r.status == 200:
                data = await r.json()
                for row in data.get("results", []):
                    total = int(row.get("capacity") or 0)
                    free  = int(row.get("numdocksavailable") or 0)
                    bikes = int(row.get("numbikesavailable") or 0)
                    if not total or row.get("is_installed") != "OUI":
                        continue
                    occ = total - free
                    geo = row.get("coordonnees_geo") or {}
                    lots.append(ParkingLot(
                        id=str(row.get("stationcode", "")),
                        name=(row.get("name") or "Paris Vélib'")[:50],
                        city="Paris",
                        country="FR",
                        total=total,
                        occupied=occ,
                        free=free,
                        occ_pct=_pct(occ, total),
                        lat=geo.get("lat"),
                        lon=geo.get("lon"),
                        type="bike_dock",
                    ))
    except Exception:
        pass
    return lots

async def run_poller(interval: int = 120):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                results = await asyncio.gather(
                    _fetch_tfl(session),       # London cycle docks
                    _fetch_sf(session),        # San Francisco
                    _fetch_bordeaux(session),  # Bordeaux real-time car parks
                    _fetch_cologne(session),   # Cologne car parks
                    _fetch_paris(session),     # Paris Vélib' bike share
                    return_exceptions=True,
                )
                all_lots = []
                for r in results:
                    if isinstance(r, list):
                        all_lots.extend(r)

                by_city = {}
                for lot in all_lots:
                    by_city.setdefault(lot.city, []).append(lot)

                # city-level summary
                summary = {}
                for city, city_lots in by_city.items():
                    with_data = [l for l in city_lots if l.occ_pct is not None]
                    summary[city] = {
                        "lots":     len(city_lots),
                        "country":  city_lots[0].country if city_lots else "",
                        "total":    sum(l.total for l in city_lots),
                        "free":     sum(l.free or 0 for l in city_lots if l.free is not None),
                        "live":     len(with_data),
                        "avg_occ":  round(sum(l.occ_pct for l in with_data) / len(with_data), 1) if with_data else None,
                    }

                _state.lots    = sorted(all_lots, key=lambda l: (l.city, l.name))
                _state.by_city = by_city
                _state.summary = summary
                _state.updated = time.time()
                _state.error   = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
