"""
Ship tracking — aisstream.io WebSocket (global, free key required).

Set AISSTREAM_KEY in .env (free at https://aisstream.io). The old no-key
regional fallbacks (Kystverket, Danish Maritime Authority) were removed —
both public REST endpoints now return 404.
"""

import asyncio
import os
import json
import time
import websockets
from dataclasses import dataclass, field
from typing import Optional

AISSTREAM_KEY = os.environ.get("AISSTREAM_KEY", "")
AISSTREAM_WS  = "wss://stream.aisstream.io/v0/stream"

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
        return f"Type {self.vessel_type}" if self.vessel_type else "Unknown"

    @property
    def status_name(self) -> str:
        return NAVIGATIONAL_STATUS.get(self.nav_status, "Unknown")

    @property
    def heading_arrow(self) -> str:
        val = self.course if self.course is not None else self.heading
        if val is None:
            return "·"
        arrows = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]
        return arrows[round(val / 45) % 8]


@dataclass
class ShipState:
    vessels: list = field(default_factory=list)
    total: int = 0
    underway: int = 0
    updated: float = field(default_factory=time.time)
    source: str = "none"
    error: Optional[str] = None


_state = ShipState()


def get_ships() -> ShipState:
    return _state


async def _run_aisstream():
    """Real-time global AIS via aisstream.io free WebSocket. Runs forever."""
    global _state
    vessels: dict[str, Vessel] = {}
    msg_count = 0
    last_snapshot = time.time()

    while True:
        try:
            async with websockets.connect(
                AISSTREAM_WS,
                ping_interval=20,
                ping_timeout=15,
                open_timeout=15,
            ) as ws:
                await ws.send(json.dumps({
                    "APIKey": AISSTREAM_KEY,
                    "BoundingBoxes": [[[-90, -180], [90, 180]]],
                    "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
                }))

                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                        mtype = msg.get("MessageType")
                        meta  = msg.get("MetaData", {})
                        mmsi  = str(meta.get("MMSI", ""))
                        if not mmsi or mmsi == "0":
                            continue

                        if mtype == "PositionReport":
                            pr  = msg["Message"]["PositionReport"]
                            lat = meta.get("latitude")
                            lon = meta.get("longitude")
                            if lat is None or lon is None or abs(float(lat)) > 90:
                                continue

                            sog = pr.get("SpeedOverGround")
                            cog = pr.get("CourseOverGround")
                            th  = pr.get("TrueHeading")

                            v = vessels.get(mmsi) or Vessel(
                                mmsi=mmsi,
                                name=meta.get("ShipName", "").strip(),
                                callsign="", vessel_type=0,
                                lat=None, lon=None,
                                speed_kts=None, course=None, heading=None,
                            )
                            v.lat        = float(lat)
                            v.lon        = float(lon)
                            v.speed_kts  = float(sog) if sog is not None and sog < 102 else None
                            v.course     = float(cog) if cog is not None and cog < 360 else None
                            v.heading    = float(th)  if th  is not None and th  != 511 else None
                            v.nav_status = pr.get("NavigationalStatus", 15)  # 15 = not defined
                            v.updated    = time.time()
                            vessels[mmsi] = v

                        elif mtype == "ShipStaticData":
                            sd = msg["Message"]["ShipStaticData"]
                            v  = vessels.get(mmsi) or Vessel(
                                mmsi=mmsi, name="", callsign="",
                                vessel_type=0, lat=None, lon=None,
                                speed_kts=None, course=None, heading=None,
                            )
                            v.name        = (sd.get("Name") or v.name or "").strip()
                            v.callsign    = (sd.get("CallSign") or "").strip()
                            v.vessel_type = sd.get("TypeOfShipAndCargoType") or 0
                            v.destination = (sd.get("Destination") or "").strip()
                            vessels[mmsi] = v

                        msg_count += 1
                        now = time.time()
                        if msg_count % 300 == 0 or (now - last_snapshot) > 10:
                            vlist = [v for v in vessels.values()
                                     if v.lat is not None and v.lon is not None]
                            _state = ShipState(
                                vessels=vlist,
                                total=len(vlist),
                                underway=sum(1 for v in vlist if (v.speed_kts or 0) > 0.5 or v.nav_status in (0, 8)),
                                source="aisstream.io",
                                updated=now,
                            )
                            last_snapshot = now

                    except Exception:
                        continue

        except Exception as e:
            _state.error = f"aisstream reconnecting: {e}"
            await asyncio.sleep(15)


async def run_poller(interval: int = 30):
    if AISSTREAM_KEY:
        await _run_aisstream()
        return
    _state.error = ("No AISSTREAM_KEY — ship tracking disabled. "
                    "Get a free key at aisstream.io")
