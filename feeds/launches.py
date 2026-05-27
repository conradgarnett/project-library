"""Rocket launch data — Launch Library 2 (The Space Devs, free, no key)."""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class LaunchState:
    upcoming: list = field(default_factory=list)
    recent:   list = field(default_factory=list)
    updated:  float = 0.0
    error:    Optional[str] = None

_state = LaunchState()

def get_launches():
    return _state

def _parse_launch(l: dict) -> dict:
    from datetime import datetime, timezone
    net = l.get("net", "")
    try:
        dt = datetime.fromisoformat(net.replace("Z", "+00:00"))
        t_minus_s = int((dt - datetime.now(timezone.utc)).total_seconds())
        if t_minus_s > 0:
            h, rem = divmod(t_minus_s, 3600)
            m, s   = divmod(rem, 60)
            if h > 48:
                countdown = f"T-{h//24}d {h%24}h"
            else:
                countdown = f"T-{h:02d}:{m:02d}:{s:02d}"
        else:
            countdown = "Launched"
    except Exception:
        countdown = "—"

    rocket = l.get("rocket", {}).get("configuration", {})
    mission = l.get("mission") or {}
    pad    = l.get("pad", {})
    loc    = pad.get("location", {})
    vid_urls = [v.get("url","") for v in l.get("vidURLs",[])[:2]]

    return {
        "id":          l.get("id",""),
        "name":        l.get("name","")[:60],
        "status":      l.get("status",{}).get("name",""),
        "net":         net[:16].replace("T"," "),
        "countdown":   countdown,
        "vehicle":     rocket.get("full_name","")[:30],
        "family":      rocket.get("family",""),
        "mission_name":mission.get("name","")[:40],
        "mission_type":mission.get("type",""),
        "pad":         pad.get("name","")[:30],
        "location":    loc.get("name","")[:30],
        "lat":         pad.get("latitude"),
        "lon":         pad.get("longitude"),
        "agency":      l.get("launch_service_provider",{}).get("name","")[:30],
        "image":       l.get("image",""),
        "videos":      vid_urls,
    }

async def run_poller(interval: int = 1800):
    global _state
    BASE = "https://ll.thespacedevs.com/2.2.0"
    while True:
        try:
            async with aiohttp.ClientSession(headers={"User-Agent":"OpenBloombergTerminal/2.0"}) as session:
                # Upcoming
                async with session.get(
                    f"{BASE}/launch/upcoming/?limit=25&mode=detailed",
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as r:
                    if r.status == 200:
                        d = await r.json()
                        _state.upcoming = [_parse_launch(l) for l in d.get("results",[])]

                # Previous
                await asyncio.sleep(5)   # rate limit: 15 req/hr
                async with session.get(
                    f"{BASE}/launch/previous/?limit=20&mode=detailed",
                    timeout=aiohttp.ClientTimeout(total=20)
                ) as r:
                    if r.status == 200:
                        d = await r.json()
                        _state.recent = [_parse_launch(l) for l in d.get("results",[])]

            _state.updated = time.time()
            _state.error = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
