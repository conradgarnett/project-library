"""Rocket launch data — rocketlaunch.live (free, no key) primary; SpaceDevs fallback."""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

RLL_BASE = "https://fdo.rocketlaunch.live/json/launches"
LL2_BASE = "https://ll.thespacedevs.com/2.2.0"

@dataclass
class LaunchState:
    upcoming: list = field(default_factory=list)
    recent:   list = field(default_factory=list)
    updated:  float = 0.0
    error:    Optional[str] = None

_state = LaunchState()

def get_launches():
    return _state


def _countdown(t0: str) -> str:
    try:
        dt = datetime.fromisoformat(t0.replace("Z", "+00:00"))
        secs = int((dt - datetime.now(timezone.utc)).total_seconds())
        if secs <= 0:
            return "Launched"
        h, rem = divmod(secs, 3600)
        m, s   = divmod(rem, 60)
        return f"T-{h//24}d {h%24}h" if h > 48 else f"T-{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        return "—"


def _parse_rll(l: dict) -> dict:
    t0  = l.get("t0") or ""
    pad = l.get("pad") or {}
    loc = pad.get("location") or {}
    missions = l.get("missions") or [{}]
    return {
        "id":          str(l.get("id", "")),
        "name":        (l.get("name") or "")[:60],
        "status":      "Go" if t0 else l.get("date_str", "TBD"),
        "net":         t0[:16].replace("T", " "),
        "countdown":   _countdown(t0) if t0 else "TBD",
        "vehicle":     (l.get("vehicle") or {}).get("name", "")[:30],
        "family":      "",
        "mission_name":(missions[0].get("name") or "")[:40],
        "mission_type":"",
        "pad":         pad.get("name", "")[:30],
        "location":    loc.get("name", "")[:30],
        "agency":      (l.get("provider") or {}).get("name", "")[:30],
        "image":       "",
        "videos":      [],
        "description": (l.get("launch_description") or "")[:200],
    }


def _parse_ll2(l: dict) -> dict:
    net     = l.get("net", "")
    rocket  = l.get("rocket", {}).get("configuration", {})
    mission = l.get("mission") or {}
    pad     = l.get("pad", {})
    loc     = pad.get("location", {})
    return {
        "id":          l.get("id", ""),
        "name":        l.get("name", "")[:60],
        "status":      l.get("status", {}).get("name", ""),
        "net":         net[:16].replace("T", " "),
        "countdown":   _countdown(net),
        "vehicle":     rocket.get("full_name", "")[:30],
        "family":      rocket.get("family", ""),
        "mission_name":mission.get("name", "")[:40],
        "mission_type":mission.get("type", ""),
        "pad":         pad.get("name", "")[:30],
        "location":    loc.get("name", "")[:30],
        "agency":      l.get("launch_service_provider", {}).get("name", "")[:30],
        "image":       l.get("image", ""),
        "videos":      [v.get("url", "") for v in l.get("vidURLs", [])[:2]],
        "description": "",
    }


async def _fetch_rll(session: aiohttp.ClientSession) -> tuple[list, list]:
    """Primary source: rocketlaunch.live — free, no key, no rate limit."""
    upcoming, recent = [], []
    try:
        async with session.get(f"{RLL_BASE}/next/15",
            timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status == 200:
                d = await r.json()
                upcoming = [_parse_rll(l) for l in d.get("result", [])]
    except Exception:
        pass
    # /past/ requires an API key on rocketlaunch.live; leave recent empty
    return upcoming, recent


async def _fetch_ll2(session: aiohttp.ClientSession) -> tuple[list, list]:
    """Fallback: SpaceDevs Launch Library 2 — 15 req/hr free tier."""
    upcoming, recent = [], []
    try:
        async with session.get(f"{LL2_BASE}/launch/upcoming/?limit=15&mode=list",
            timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                d = await r.json()
                upcoming = [_parse_ll2(l) for l in d.get("results", [])]
    except Exception:
        pass
    try:
        await asyncio.sleep(2)
        async with session.get(f"{LL2_BASE}/launch/previous/?limit=10&mode=list",
            timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                d = await r.json()
                recent = [_parse_ll2(l) for l in d.get("results", [])]
    except Exception:
        pass
    return upcoming, recent


async def run_poller(interval: int = 1800):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                upcoming, recent = await _fetch_rll(session)
                if not upcoming:
                    upcoming, recent = await _fetch_ll2(session)
                _state.upcoming = upcoming
                _state.recent   = recent
                _state.updated  = time.time()
                _state.error    = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
