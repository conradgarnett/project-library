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

# ── TfL London ────────────────────────────────────────────────────────────────
async def _fetch_tfl(session):
    lots = []
    try:
        async with session.get(
            "https://api.tfl.gov.uk/Occupancy/CarPark",
            timeout=aiohttp.ClientTimeout(total=15)
        ) as r:
            if r.status == 200:
                data = await r.json()
                for p in data:
                    bays = p.get("bays", [])
                    total = sum(b.get("bayCount", 0) for b in bays)
                    free  = sum(b.get("free", 0) for b in bays if not b.get("bayType","").lower().startswith("dis"))
                    occ   = total - free if total else None
                    coords = p.get("centrePoint", [])
                    lat = coords[0] if len(coords) > 0 else None
                    lon = coords[1] if len(coords) > 1 else None
                    lots.append(ParkingLot(
                        id=p.get("id",""),
                        name=p.get("name","")[:50],
                        city="London",
                        country="GB",
                        total=total,
                        occupied=occ,
                        free=free,
                        occ_pct=_pct(occ, total),
                        lat=lat, lon=lon,
                        type="garage",
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

# ── Leeds UK ──────────────────────────────────────────────────────────────────
async def _fetch_leeds(session):
    lots = []
    try:
        async with session.get(
            "https://datamillnorth.org/api/table/wheatfields/api/v0/tables/car-park-live/rows/?$limit=30",
            timeout=aiohttp.ClientTimeout(total=12)
        ) as r:
            if r.status == 200:
                data = await r.json()
                rows = data if isinstance(data, list) else data.get("rows", data.get("data", []))
                for row in rows:
                    total = int(row.get("capacity", row.get("spaces", 0)) or 0)
                    free  = int(row.get("spaces_available", row.get("free", 0)) or 0)
                    if not total: total = max(free, 1)
                    occ = total - free
                    lots.append(ParkingLot(
                        id=str(row.get("id", row.get("car_park_id", ""))),
                        name=(row.get("name", row.get("car_park_name", "Leeds Car Park")) or "Leeds Car Park")[:50],
                        city="Leeds",
                        country="GB",
                        total=total,
                        occupied=occ,
                        free=free,
                        occ_pct=_pct(occ, total),
                        lat=float(row.get("latitude", 0) or 0) or None,
                        lon=float(row.get("longitude", 0) or 0) or None,
                    ))
    except Exception:
        pass
    return lots

# ── Birmingham UK ─────────────────────────────────────────────────────────────
async def _fetch_birmingham(session):
    lots = []
    try:
        async with session.get(
            "https://api.birmingham.gov.uk/v1/transport/parking/car-parks",
            timeout=aiohttp.ClientTimeout(total=12)
        ) as r:
            if r.status == 200:
                data = await r.json()
                items = data if isinstance(data, list) else data.get("features", data.get("data", []))
                for item in items:
                    props = item.get("properties", item)
                    total = int(props.get("totalSpaces", props.get("capacity", 0)) or 0)
                    free  = int(props.get("availableSpaces", props.get("free", 0)) or 0)
                    if not total: continue
                    occ = total - free
                    geom = item.get("geometry", {})
                    coords = geom.get("coordinates", []) if geom else []
                    lat = coords[1] if len(coords) > 1 else None
                    lon = coords[0] if len(coords) > 0 else None
                    lots.append(ParkingLot(
                        id=str(props.get("id", props.get("carparkId", ""))),
                        name=(props.get("name", props.get("carparkName", "Birmingham Car Park")) or "Birmingham Car Park")[:50],
                        city="Birmingham",
                        country="GB",
                        total=total,
                        occupied=occ,
                        free=free,
                        occ_pct=_pct(occ, total),
                        lat=lat, lon=lon,
                    ))
    except Exception:
        pass
    return lots

# ── Cologne / Köln DE ─────────────────────────────────────────────────────────
async def _fetch_cologne(session):
    lots = []
    try:
        async with session.get(
            "https://offenedaten-koeln.de/api/3/action/datastore_search"
            "?resource_id=f5e4fdca-6b41-4a2d-855b-8f6fac24f13b&limit=50",
            timeout=aiohttp.ClientTimeout(total=12)
        ) as r:
            if r.status == 200:
                data = await r.json()
                records = data.get("result", {}).get("records", [])
                for row in records:
                    total = int(row.get("KAPAZITAET", row.get("Kapazitaet", 0)) or 0)
                    free  = int(row.get("FREI", row.get("Frei", 0)) or 0)
                    if not total: continue
                    occ = total - free
                    lots.append(ParkingLot(
                        id=str(row.get("_id", row.get("ID", ""))),
                        name=(row.get("NAME", row.get("Parkplatz", "Köln Parkhaus")) or "Köln Parkhaus")[:50],
                        city="Cologne",
                        country="DE",
                        total=total,
                        occupied=occ,
                        free=free,
                        occ_pct=_pct(occ, total),
                        lat=float(row.get("LAT", 0) or 0) or None,
                        lon=float(row.get("LON", 0) or 0) or None,
                    ))
    except Exception:
        pass
    return lots

# ── Newcastle UK ──────────────────────────────────────────────────────────────
async def _fetch_newcastle(session):
    lots = []
    try:
        async with session.get(
            "https://api.newcastle.gov.uk/api/v1/parking",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            if r.status == 200:
                data = await r.json()
                items = data if isinstance(data, list) else data.get("data", [])
                for row in items:
                    total = int(row.get("capacity", row.get("spaces", 0)) or 0)
                    free  = int(row.get("available", row.get("free", 0)) or 0)
                    if not total: continue
                    lots.append(ParkingLot(
                        id=str(row.get("id", "")),
                        name=(row.get("name", "Newcastle Car Park") or "Newcastle Car Park")[:50],
                        city="Newcastle",
                        country="GB",
                        total=total,
                        occupied=total - free,
                        free=free,
                        occ_pct=_pct(total - free, total),
                        lat=float(row.get("lat", 0) or 0) or None,
                        lon=float(row.get("lng", row.get("lon", 0)) or 0) or None,
                    ))
    except Exception:
        pass
    return lots

# ── Chicago (locations only — no live occupancy but useful reference) ──────────
async def _fetch_chicago(session):
    lots = []
    try:
        async with session.get(
            "https://data.cityofchicago.org/resource/t4tf-f5xu.json?$limit=60",
            timeout=aiohttp.ClientTimeout(total=12)
        ) as r:
            if r.status == 200:
                data = await r.json()
                for row in data:
                    total = int(row.get("total_spaces", row.get("spaces", 0)) or 0)
                    if not total: continue
                    lots.append(ParkingLot(
                        id=str(row.get("systemcodeid", row.get("objectid", ""))),
                        name=(row.get("facilityname", row.get("address", "Chicago Garage")) or "Chicago Garage")[:50],
                        city="Chicago",
                        country="US",
                        total=total,
                        occupied=None,
                        free=None,
                        occ_pct=None,
                        lat=float(row.get("latitude", 0) or 0) or None,
                        lon=float(row.get("longitude", 0) or 0) or None,
                        type="garage",
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
                    _fetch_tfl(session),
                    _fetch_sf(session),
                    _fetch_leeds(session),
                    _fetch_birmingham(session),
                    _fetch_cologne(session),
                    _fetch_newcastle(session),
                    _fetch_chicago(session),
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
