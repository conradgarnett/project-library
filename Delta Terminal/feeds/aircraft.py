"""Live aircraft positions — FlightRadar24 public API via FlightRadarAPI library."""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Aircraft:
    icao24: str
    callsign: str
    origin_country: str
    longitude: Optional[float]
    latitude: Optional[float]
    altitude_m: Optional[float]
    on_ground: bool
    velocity_ms: Optional[float]
    heading: Optional[float]
    vertical_rate: Optional[float]
    aircraft_type: str = ""
    registration: str = ""
    origin_airport: str = ""
    destination_airport: str = ""
    last_contact: float = 0.0

    @property
    def altitude_ft(self) -> Optional[float]:
        return self.altitude_m * 3.28084 if self.altitude_m else None

    @property
    def speed_kts(self) -> Optional[float]:
        return self.velocity_ms * 1.94384 if self.velocity_ms else None

    @property
    def heading_arrow(self) -> str:
        if self.heading is None:
            return "·"
        arrows = ["↑", "↗", "→", "↘", "↓", "↙", "←", "↖"]
        return arrows[round(self.heading / 45) % 8]

    @property
    def fl(self) -> str:
        if self.on_ground:
            return "GND"
        if self.altitude_ft is None:
            return "---"
        return f"FL{int(self.altitude_ft / 100):03d}"


@dataclass
class AircraftState:
    aircraft: list = field(default_factory=list)
    total: int = 0
    airborne: int = 0
    updated: float = field(default_factory=time.time)
    source: str = "none"
    error: Optional[str] = None


_state = AircraftState()


def get_aircraft() -> AircraftState:
    return _state


def _fetch_fr24() -> list[Aircraft]:
    from FlightRadarAPI import FlightRadar24API
    api = FlightRadar24API()
    flights = api.get_flights()
    planes = []
    for f in flights:
        try:
            lat = f.latitude
            lon = f.longitude
            if lat is None or lon is None:
                continue
            alt_ft = float(f.altitude) if f.altitude else None
            alt_m  = alt_ft * 0.3048 if alt_ft else None
            gs     = float(f.ground_speed) if f.ground_speed else None
            vel_ms = gs * 0.514444 if gs else None
            vs     = float(f.vertical_speed) if f.vertical_speed else None
            vert_ms = vs * 0.00508 if vs else None
            hdg    = float(f.heading) if f.heading else None
            planes.append(Aircraft(
                icao24=str(f.icao_24bit or f.id or ""),
                callsign=str(f.callsign or "").strip(),
                origin_country="",
                longitude=float(lon),
                latitude=float(lat),
                altitude_m=alt_m,
                on_ground=bool(f.on_ground),
                velocity_ms=vel_ms,
                heading=hdg,
                vertical_rate=vert_ms,
                aircraft_type=str(f.aircraft_code or ""),
                registration=str(f.registration or ""),
                origin_airport=str(f.origin_airport_iata or ""),
                destination_airport=str(f.destination_airport_iata or ""),
                last_contact=time.time(),
            ))
        except Exception:
            continue
    return planes


async def run_poller(interval: int = 30):
    global _state
    loop = asyncio.get_event_loop()
    while True:
        try:
            planes = await loop.run_in_executor(None, _fetch_fr24)
            _state = AircraftState(
                aircraft=planes,
                total=len(planes),
                airborne=sum(1 for p in planes if not p.on_ground),
                updated=time.time(),
                source="flightradar24",
            )
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
