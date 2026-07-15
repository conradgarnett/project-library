"""GDELT 2.0 event feed — free, no API key.

Downloads the latest 15-minute export CSVs and filters for:
  - POL: political events (CAMEO codes 10, 13, 14, 15, 16, 17)
  - TER: security/attack events (CAMEO codes 18, 19, 20)

Accumulates ~2 hours of events (8 files) to maintain a live rolling window.
"""
import asyncio
import aiohttp
import io
import time
import zipfile
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

GDELT_MASTER = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

# CAMEO root codes → human label
CAMEO_LABELS = {
    "01": "Statement",
    "02": "Appeal",
    "03": "Cooperate",
    "04": "Consult",
    "05": "Diplomacy",
    "06": "Material Aid",
    "07": "Aid",
    "08": "Yield",
    "09": "Investigate",
    "10": "Demand",
    "11": "Disapprove",
    "12": "Reject",
    "13": "Threaten",
    "14": "Protest",
    "15": "Force Display",
    "16": "Reduce Relations",
    "17": "Coerce",
    "18": "Assault",
    "19": "Fight",
    "20": "Mass Violence",
}

# Finer event codes 26-col for descriptive label
CAMEO_FINE = {
    "200": "Mass Violence",
    "201": "Hostage Taking",
    "202": "Suicide Bombing",
    "203": "IED/Roadside Bomb",
    "204": "Vehicular Attack",
    "205": "Mortar/Missile Attack",
    "206": "Small Arms Attack",
    "207": "Bombing/Explosion",
    "208": "Attack (unspecified)",
    "180": "Assault",
    "181": "Abduct/Disappear",
    "182": "Torture",
    "183": "Kill",
    "185": "Physically Assault",
    "186": "Sexual Violence",
    "190": "Use Conventional Force",
    "191": "Impose Blockade",
    "192": "Occupy Territory",
    "193": "Fight with Small Arms",
    "194": "Artillery/Airstrike",
    "195": "Naval Attack",
    "196": "Violate Ceasefire",
    "130": "Threaten",
    "131": "Threaten Non-Force",
    "132": "Threaten Admin Sanctions",
    "133": "Threaten Political Abuse",
    "134": "Threaten Military",
    "135": "Threaten Unconventional Action",
    "136": "Threaten Violent Repression",
    "138": "Threaten Military Force",
    "140": "Protest",
    "141": "Demonstrate/Rally",
    "142": "Conduct Hunger Strike",
    "143": "Conduct Strike/Boycott",
    "144": "Obstruct/Block",
    "145": "Protest Violently",
    "100": "Demand",
    "101": "Demand Rights",
    "160": "Reduce Relations",
    "161": "Reduce Diplomatic Relations",
    "162": "Sever Diplomatic Relations",
    "163": "Halt Negotiations",
    "164": "Halt Mediation",
    "165": "Expel/Withdraw",
    "166": "Impose Embargo/Sanctions",
    "170": "Coerce",
    "171": "Seize/Confiscate",
    "172": "Arrest/Detain",
    "173": "Administrative Detention",
    "174": "Expel/Deport",
    "175": "Use Tactics of Political Repression",
}

POL_ROOT_CODES = {"10", "11", "12", "13", "14", "15", "16", "17"}
TER_ROOT_CODES = {"18", "19", "20"}
DIP_ROOT_CODES = {"03", "04", "05", "06", "07", "08", "09"}

ALL_ROOT_CODES = POL_ROOT_CODES | TER_ROOT_CODES | DIP_ROOT_CODES


@dataclass
class GdeltEvent:
    event_id:   str
    day:        str
    event_code: str
    root_code:  str
    quad_class: int
    goldstein:  float
    mentions:   int
    articles:   int
    avg_tone:   float
    location:   str
    country:    str
    lat:        Optional[float]
    lon:        Optional[float]
    actor1:     str
    actor2:     str
    url:        str
    label:      str
    added:      str


@dataclass
class GdeltState:
    pol:     list = field(default_factory=list)   # political events
    ter:     list = field(default_factory=list)   # security/attack events
    dip:     list = field(default_factory=list)   # diplomatic/cooperative events
    updated: float = 0.0
    error:   Optional[str] = None


_state = GdeltState()


def get_gdelt():
    return _state


def _prev_file_url(url: str, steps: int) -> str:
    """Compute URL for N steps of 15 minutes before this one."""
    # URL format: .../YYYYMMDDHHMMSS.export.CSV.zip
    base = url.rsplit("/", 1)[0]
    fname = url.rsplit("/", 1)[1]
    ts_str = fname.split(".")[0]
    dt = datetime.strptime(ts_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    prev = dt - timedelta(minutes=15 * steps)
    return f"{base}/{prev.strftime('%Y%m%d%H%M%S')}.export.CSV.zip"


def _parse_csv_zip(data: bytes) -> list[GdeltEvent]:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        fname = z.namelist()[0]
        content = z.read(fname).decode("utf-8", "replace")
    except Exception:
        return []

    events = []
    for line in content.splitlines():
        parts = line.split("\t")
        if len(parts) < 61:
            continue
        root = parts[28]
        if root not in ALL_ROOT_CODES:
            continue

        try:
            goldstein = float(parts[30]) if parts[30] else 0.0
            mentions  = int(parts[31])   if parts[31] else 0
            articles  = int(parts[33])   if parts[33] else 0
            avg_tone  = float(parts[34]) if parts[34] else 0.0
            quad      = int(parts[29])   if parts[29] else 0
            lat = float(parts[56]) if parts[56] else None
            lon = float(parts[57]) if parts[57] else None
        except (ValueError, IndexError):
            continue

        code = parts[26]
        label = CAMEO_FINE.get(code, CAMEO_LABELS.get(root, root))
        actor1 = parts[6] or parts[5] or ""
        actor2 = parts[17] or parts[16] or ""

        events.append(GdeltEvent(
            event_id   = parts[0],
            day        = parts[1],
            event_code = code,
            root_code  = root,
            quad_class = quad,
            goldstein  = goldstein,
            mentions   = mentions,
            articles   = articles,
            avg_tone   = avg_tone,
            location   = parts[52] or parts[36] or "",
            country    = parts[53] or parts[37] or "",
            lat        = lat,
            lon        = lon,
            actor1     = actor1.title(),
            actor2     = actor2.title(),
            url        = parts[60],
            label      = label,
            added      = parts[59],
        ))

    return events


async def _fetch_file(session: aiohttp.ClientSession, url: str) -> bytes:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
            if r.status == 200:
                return await r.read()
    except Exception:
        pass
    return b""


async def run_poller(interval: int = 1800):
    """Refresh every 30 minutes — download 8 files (2 hours of data)."""
    global _state
    async with aiohttp.ClientSession(
        headers={"User-Agent": "OpenBloombergTerminal/2.0 (mailto:info@openbloomberg.io)"}
    ) as session:
        while True:
            try:
                async with session.get(GDELT_MASTER, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    text = await r.text()
                latest_url = text.strip().splitlines()[0].split()[-1]

                urls = [latest_url] + [_prev_file_url(latest_url, i) for i in range(1, 8)]
                tasks = [_fetch_file(session, u) for u in urls]
                results = await asyncio.gather(*tasks)

                all_events: list[GdeltEvent] = []
                seen_urls: set[str] = set()
                for data in results:
                    if data:
                        for ev in _parse_csv_zip(data):
                            if ev.url and ev.url not in seen_urls:
                                seen_urls.add(ev.url)
                                all_events.append(ev)

                def ev_dict(e: GdeltEvent) -> dict:
                    return {
                        "event_id":   e.event_id,
                        "day":        e.day,
                        "event_code": e.event_code,
                        "root_code":  e.root_code,
                        "label":      e.label,
                        "quad_class": e.quad_class,
                        "goldstein":  e.goldstein,
                        "mentions":   e.mentions,
                        "articles":   e.articles,
                        "avg_tone":   e.avg_tone,
                        "location":   e.location,
                        "country":    e.country,
                        "lat":        e.lat,
                        "lon":        e.lon,
                        "actor1":     e.actor1,
                        "actor2":     e.actor2,
                        "url":        e.url,
                        "added":      e.added,
                    }

                pol_evs = [e for e in all_events if e.root_code in POL_ROOT_CODES]
                ter_evs = [e for e in all_events if e.root_code in TER_ROOT_CODES]
                dip_evs = [e for e in all_events if e.root_code in DIP_ROOT_CODES]

                pol_sorted = sorted(pol_evs, key=lambda e: e.mentions, reverse=True)[:100]
                ter_sorted = sorted(ter_evs, key=lambda e: e.mentions, reverse=True)[:100]
                dip_sorted = sorted(dip_evs, key=lambda e: e.mentions, reverse=True)[:100]

                _state.pol     = [ev_dict(e) for e in pol_sorted]
                _state.ter     = [ev_dict(e) for e in ter_sorted]
                _state.dip     = [ev_dict(e) for e in dip_sorted]
                _state.updated = time.time()
                _state.error   = None

            except Exception as exc:
                _state.error = str(exc)

            await asyncio.sleep(interval)
