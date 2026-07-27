"""
Cloudflare Radar — BGP routing intelligence
Requires: CLOUDFLARE_API_KEY in environment

Working endpoints (confirmed):
  - /radar/bgp/leaks/events      BGP route leak events
  - /radar/bgp/routes/stats      Global BGP routing statistics

Base: https://api.cloudflare.com/client/v4/radar
"""
import asyncio, aiohttp, os, time
from dataclasses import dataclass, field
from typing import Optional

CF_BASE = "https://api.cloudflare.com/client/v4/radar"


@dataclass
class CloudflareState:
    bgp_leaks:   list          = field(default_factory=list)
    bgp_stats:   dict          = field(default_factory=dict)
    updated:     float         = 0.0
    error:       Optional[str] = None


_state = CloudflareState()


def get_cloudflare():
    return _state


def _headers() -> dict:
    key = os.environ.get("CLOUDFLARE_API_KEY", "")
    h = {"User-Agent": "OpenBloombergTerminal/2.0"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


async def _get(session: aiohttp.ClientSession, path: str, params: dict = None) -> dict:
    url = CF_BASE + path
    async with session.get(
        url, headers=_headers(), params=params or {},
        timeout=aiohttp.ClientTimeout(total=15)
    ) as r:
        if r.status != 200:
            return {}
        data = await r.json()
        return data.get("result", data)


async def run_poller(interval: int = 3600):
    global _state
    while True:
        key = os.environ.get("CLOUDFLARE_API_KEY", "")
        if not key:
            _state.error = "CLOUDFLARE_API_KEY not set"
            await asyncio.sleep(interval)
            continue
        try:
            async with aiohttp.ClientSession() as session:
                leaks_raw = await _get(session, "/bgp/leaks/events", {"limit": 50})
                await asyncio.sleep(0.5)
                stats_raw = await _get(session, "/bgp/routes/stats")

            # Parse leak events — API shape: result.events, snake_case fields
            # (id, leak_asn, leak_count, peer_count, origin_count, leak_seg,
            #  detected_ts, countries)
            bgp_leaks = []
            for event in (leaks_raw.get("events") or []):
                seg = event.get("leak_seg") or []
                bgp_leaks.append({
                    "id":         event.get("id", ""),
                    "date":       (event.get("detected_ts", "") or "")[:10],
                    "leak_asn":   event.get("leak_asn", 0),
                    "prefixes":   event.get("leak_count", 0),
                    "peers":      event.get("peer_count", 0),
                    "countries":  event.get("countries", []),
                    "origin_asn": seg[0] if seg else "",
                })

            # Parse BGP route stats — API shape: result.stats with
            # distinct_prefixes / distinct_origins / routes_valid / routes_invalid
            stats = stats_raw.get("stats") or {}
            bgp_stats = {
                "total_prefixes":   stats.get("distinct_prefixes", 0),
                "distinct_origins": stats.get("distinct_origins", 0),
                "invalid_routes":   stats.get("routes_invalid", 0),
                "rpki_valid":       stats.get("routes_valid", 0),
                "rpki_invalid":     stats.get("routes_invalid", 0),
            }

            _state.bgp_leaks = bgp_leaks
            _state.bgp_stats = bgp_stats
            _state.updated   = time.time()
            _state.error     = None

        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
