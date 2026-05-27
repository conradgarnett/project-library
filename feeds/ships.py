"""
Ship tracking via public AIS TCP streams + Marine Traffic public feed.
No API key required — connects to community-run AIS aggregators.

Primary:   AISHub public feed (TCP, NMEA sentences)
Fallback:  kystverket.no REST API (Norwegian waters, no key)
           Danish Maritime Authority open AIS
"""

import asyncio
import time
import aiohttp
from dataclasses import dataclass, field
from typing import Optional

# Public AIS TCP feeds (community aggregators, no registration required)
# These are volunteer-operated; availability varies
AIS_TCP_HOSTS = [
    ("153.44.253.27", 5631),   # commonly listed public AIS feed
    ("data.aishub.net", 2101),  # AISHub sample stream
]

# Norwegian Coastal Administration open AIS REST (Norwegian waters)
KYSTVERKET_URL = "https://kystverket.no/globalassets/filer/kart/ais-kystverket-api-doc.pdf"
KYSTVERKET_API = "https://api.kystverket.no/ais/v1/boundingbox?north=72&south=57&east=31&west=4&limit=100"

# Denmark Maritime Authority
DANISH_AIS = "https://api.dma.dk/v1/vessels?limit=100"

NAVIGATIONAL_STATUS = {
    0: "Under way (engine)", 1: "At anchor", 2: "Not under command",
    3: "Restricted maneuverability", 4: "Constrained by draught",
    5: "Moored", 6: "Aground", 7: "Engaged in fishing",
    8: "Under way (sailing)", 15: "Not defined",
}

SHIP_TYPES = {
    20: "Wing in ground", 21: "WIG hazmat A", 22: "WIG hazmat B",
    30: "Fishing", 31: "Towing", 32: "Towing (large)", 33: "Dredging",
    36: "Sailing", 37: "Pleasure craft",
    40: "High speed craft", 50: "Pilot vessel", 51: "Search and rescue",
    52: "Tug", 53: "Port tender", 55: "Law enforcement",
    60: "Passenger", 70: "Cargo", 80: "Tanker", 90: "Other",
}


@dataclass
class Vessel:
    mmsi: str
    name: str
    callsign: str
    vessel_type: int
    lat: Optional[float]
    lon: Optional[float]
    speed_kts: Optional[float]
    course: Optional[float]
    heading: Optional[float]
    nav_status: int = 0
    destination: str = ""
    flag: str = ""
    length: Optional[float] = None
    updated: float = field(default_factory=time.time)

    @property
    def type_name(self) -> str:
        for k, v in SHIP_TYPES.items():
            if self.vessel_type >= k and self.vessel_type < k + 10:
                return v
        return f"Type {self.vessel_type}"

    @property
    def status_name(self) -> str:
        return NAVIGATIONAL_STATUS.get(self.nav_status, "Unknown")

    @property
    def heading_arrow(self) -> str:
        if self.course is None:
            return "·"
        arrows = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]
        return arrows[round(self.course / 45) % 8]


@dataclass
class ShipState:
    vessels: list[Vessel] = field(default_factory=list)
    total: int = 0
    underway: int = 0
    updated: float = field(default_factory=time.time)
    source: str = "none"
    error: Optional[str] = None


_state = ShipState()
_raw_sentences: list[str] = []
_sentence_lock = asyncio.Lock() if False else None  # initialized at runtime


def get_ships() -> ShipState:
    return _state


def _parse_nmea_vdm(sentence: str) -> Optional[dict]:
    """Minimal VDM/VDO parser for position reports (type 1,2,3,18)."""
    try:
        if not sentence.startswith("!AIVDM") and not sentence.startswith("!AIVDO"):
            return None
        parts = sentence.split(",")
        if len(parts) < 6:
            return None
        payload = parts[5]

        def decode_char(c: str) -> int:
            v = ord(c) - 48
            return v - 8 if v > 40 else v

        bits = "".join(f"{decode_char(c):06b}" for c in payload)

        def bits_to_int(start: int, length: int, signed: bool = False) -> int:
            b = bits[start:start + length]
            if not b:
                return 0
            val = int(b, 2)
            if signed and b[0] == "1":
                val -= (1 << length)
            return val

        msg_type = bits_to_int(0, 6)
        if msg_type not in (1, 2, 3, 18):
            return None

        mmsi = str(bits_to_int(8, 30))
        lat  = bits_to_int(89, 27, signed=True) / 600000.0 if msg_type <= 3 else bits_to_int(85, 27, signed=True) / 600000.0
        lon  = bits_to_int(61, 28, signed=True) / 600000.0 if msg_type <= 3 else bits_to_int(57, 28, signed=True) / 600000.0
        speed = bits_to_int(50, 10) / 10.0 if msg_type <= 3 else bits_to_int(46, 10) / 10.0
        course = bits_to_int(116, 12) / 10.0 if msg_type <= 3 else bits_to_int(112, 12) / 10.0
        status = bits_to_int(38, 4) if msg_type <= 3 else 0

        return {"mmsi": mmsi, "lat": lat, "lon": lon,
                "speed": speed, "course": course, "status": status,
                "msg_type": msg_type}
    except Exception:
        return None


async def _connect_tcp_stream(host: str, port: int, timeout: float = 30.0):
    """Try to connect to a public AIS TCP stream and collect sentences."""
    global _state
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=10
        )
        vessels: dict[str, Vessel] = {}
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=5)
                sentence = line.decode("ascii", errors="ignore").strip()
                parsed = _parse_nmea_vdm(sentence)
                if parsed:
                    mmsi = parsed["mmsi"]
                    v = vessels.get(mmsi, Vessel(
                        mmsi=mmsi, name="", callsign="",
                        vessel_type=0, lat=None, lon=None,
                        speed_kts=None, course=None, heading=None,
                    ))
                    v.lat   = parsed["lat"] if abs(parsed["lat"]) < 90 else None
                    v.lon   = parsed["lon"] if abs(parsed["lon"]) < 180 else None
                    v.speed_kts = parsed["speed"]
                    v.course    = parsed["course"]
                    v.nav_status = parsed["status"]
                    v.updated = time.time()
                    vessels[mmsi] = v
            except asyncio.TimeoutError:
                break
        writer.close()
        vlist = list(vessels.values())
        _state = ShipState(
            vessels=vlist,
            total=len(vlist),
            underway=sum(1 for v in vlist if v.nav_status == 0 and (v.speed_kts or 0) > 0.5),
            source=f"{host}:{port}",
            updated=time.time(),
        )
        return True
    except Exception as e:
        return False


async def _fetch_kystverket(session: aiohttp.ClientSession) -> bool:
    """Norwegian Coastal Administration AIS — Norwegian waters, no key."""
    global _state
    try:
        async with session.get(KYSTVERKET_API, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return False
            data = await r.json()
            features = data.get("features", [])
            vessels = []
            for f in features:
                p  = f.get("properties", {})
                gp = (f.get("geometry") or {}).get("coordinates", [None, None])
                vessels.append(Vessel(
                    mmsi=str(p.get("mmsi", "")),
                    name=p.get("name", ""),
                    callsign=p.get("callsign", ""),
                    vessel_type=p.get("shipType", 0),
                    lat=gp[1],
                    lon=gp[0],
                    speed_kts=p.get("speedOverGround"),
                    course=p.get("courseOverGround"),
                    heading=p.get("trueHeading"),
                    nav_status=p.get("navigationalStatus", 15),
                    destination=p.get("destination", ""),
                    flag=p.get("countryCode", ""),
                ))
            _state = ShipState(
                vessels=vessels, total=len(vessels),
                underway=sum(1 for v in vessels if v.nav_status == 0),
                source="kystverket.no (Norway)", updated=time.time(),
            )
            return True
    except Exception:
        return False


async def run_poller(interval: int = 30):
    global _state
    async with aiohttp.ClientSession(headers={"User-Agent": "OpenBloomberg/1.0"}) as session:
        while True:
            # Try TCP streams first
            connected = False
            for host, port in AIS_TCP_HOSTS:
                if await _connect_tcp_stream(host, port, timeout=20):
                    connected = True
                    break

            # Fall back to Kystverket (Norwegian waters)
            if not connected:
                if not await _fetch_kystverket(session):
                    _state.error = "AIS TCP unavailable — try AISHub free account for global coverage"
                    _state.updated = time.time()

            await asyncio.sleep(interval)
