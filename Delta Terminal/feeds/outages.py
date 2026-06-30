"""
Internet outage monitoring — RIPE NCC Routing Information Service.

RIPE Stat (free, no key): BGP updates for major transit ASNs + country routing stats.
BGPView.io (free, no key): global BGP infrastructure statistics.
"""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

RIPE_STAT = "https://stat.ripe.net/data"
BGPVIEW   = "https://api.bgpview.io"

# Major global transit / tier-1 ASNs to monitor for routing events
TRANSIT_ASNS = ["AS3356", "AS1299", "AS174", "AS2914", "AS6939"]

# Countries to watch for routing-level disruptions
MONITOR_CC = [
    "US", "DE", "GB", "JP", "CN", "FR", "BR", "IN",
    "CA", "AU", "KR", "RU", "UA", "IL", "IR", "TR",
]

CC_NAMES = {
    "US": "United States", "DE": "Germany",    "GB": "United Kingdom",
    "JP": "Japan",         "CN": "China",       "FR": "France",
    "BR": "Brazil",        "IN": "India",       "CA": "Canada",
    "AU": "Australia",     "KR": "South Korea", "RU": "Russia",
    "UA": "Ukraine",       "IL": "Israel",      "IR": "Iran",
    "TR": "Turkey",
}


@dataclass
class OutageState:
    alerts:   list  = field(default_factory=list)
    bgp:      list  = field(default_factory=list)
    countries:list  = field(default_factory=list)
    updated:  float = 0.0
    error:    Optional[str] = None


_state = OutageState()


def get_outages():
    return _state


async def _fetch_bgp_updates(session: aiohttp.ClientSession) -> list:
    """BGP announcements and withdrawals for the top 3 transit ASNs (last 2h)."""
    events = []
    for asn in TRANSIT_ASNS[:3]:
        try:
            async with session.get(
                f"{RIPE_STAT}/bgp-updates/data.json",
                params={"resource": asn, "starttime": "2h", "endtime": "now"},
                timeout=aiohttp.ClientTimeout(total=12),
            ) as r:
                if r.status != 200:
                    continue
                d = await r.json()
                updates = (d.get("data") or {}).get("updates", [])
                for u in (updates or [])[:15]:
                    attrs = u.get("attrs", {})
                    ts    = u.get("timestamp", "")
                    if ts:
                        try:
                            ts = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%H:%M UTC")
                        except Exception:
                            pass
                    path   = attrs.get("path", [])
                    origin = str(path[-1]) if path else asn.lstrip("AS")
                    events.append({
                        "prefix": attrs.get("target_prefix", attrs.get("prefix", "")),
                        "type":   u.get("type", "A"),
                        "peer":   str(attrs.get("source_id", ""))[:30],
                        "origin": f"AS{origin}" if not str(origin).startswith("AS") else origin,
                        "time":   ts,
                    })
        except Exception:
            continue
    return events[:60]


def _synthesise_alerts(bgp_events: list) -> list:
    """Generate routing alerts from BGP update withdrawal ratios per ASN."""
    from collections import Counter
    counts: dict = {}
    for e in bgp_events:
        asn = e.get("origin", "")
        if asn not in counts:
            counts[asn] = {"A": 0, "W": 0}
        counts[asn][e.get("type", "A")] += 1

    alerts = []
    now_str = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    for asn, c in counts.items():
        total      = c["A"] + c["W"]
        withdraw_r = c["W"] / total if total else 0
        if total >= 5 and withdraw_r >= 0.4:
            alerts.append({
                "type":   "asn",
                "name":   f"{asn} elevated withdrawals ({c['W']}/{total} events)",
                "code":   asn,
                "start":  now_str,
                "level":  "warning" if withdraw_r >= 0.6 else "notice",
                "score":  round(withdraw_r * 100, 1),
                "source": "RIPE NCC",
            })
    return sorted(alerts, key=lambda x: x["score"], reverse=True)


async def _fetch_country_stats(session: aiohttp.ClientSession) -> list:
    """RIPE Stat country-resource-stats — prefix and ASN counts per country (latest day only)."""
    import datetime as _dt
    today = _dt.datetime.utcnow().strftime("%Y-%m-%dT00:00:00")
    countries = []
    for cc in MONITOR_CC:
        try:
            async with session.get(
                f"{RIPE_STAT}/country-resource-stats/data.json",
                params={"resource": cc, "starttime": today, "resolution": "1d"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                if r.status != 200:
                    continue
                d      = await r.json()
                stats  = (d.get("data") or {}).get("stats", [])
                latest = stats[-1] if stats else {}
                if not latest:
                    continue
                countries.append({
                    "country": CC_NAMES.get(cc, cc),
                    "code":    cc,
                    "score":   latest.get("v4_prefixes_ris", latest.get("v4_prefixes", 0)),
                    "normal":  latest.get("v6_prefixes_ris", latest.get("v6_prefixes", 0)),
                    "asns":    latest.get("asns_ris", latest.get("asns", 0)),
                })
        except Exception:
            continue
        await asyncio.sleep(0.15)   # be courteous to RIPE Stat
    return sorted(countries, key=lambda x: x["country"])


async def run_poller(interval: int = 300):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                # BGP updates and country stats run concurrently
                bgp_task      = asyncio.create_task(_fetch_bgp_updates(session))
                countries_r   = await _fetch_country_stats(session)  # sequential — respects RIPE rate limits
                bgp_r         = await bgp_task

                _state.bgp       = bgp_r       if isinstance(bgp_r,     list) else []
                _state.alerts    = _synthesise_alerts(_state.bgp)
                _state.countries = countries_r if isinstance(countries_r, list) else []
                _state.updated   = time.time()
                _state.error     = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
