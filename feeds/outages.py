"""
Internet outage monitoring — IODA (Internet Outage Detection & Analysis).
Georgia Tech / CAIDA. Free, no API key.

Also pulls BGP hijack alerts from RIPE NCC (free, no key).
"""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Optional

@dataclass
class OutageState:
    alerts:   list  = field(default_factory=list)   # IODA outage alerts
    bgp:      list  = field(default_factory=list)   # BGP hijack events
    countries:list  = field(default_factory=list)   # country-level signal summary
    updated:  float = 0.0
    error:    Optional[str] = None

_state = OutageState()

def get_outages():
    return _state

IODA_BASE  = "https://api.ioda.caida.org/v2"
RIPE_BASE  = "https://stat.ripe.net/data"

async def _fetch_ioda_alerts(session):
    alerts = []
    try:
        now   = int(time.time())
        since = now - 86400   # last 24h
        async with session.get(
            f"{IODA_BASE}/outages/alerts",
            params={"from": since, "until": now, "limit": 100},
            timeout=aiohttp.ClientTimeout(total=15)
        ) as r:
            if r.status == 200:
                d = await r.json()
                for a in (d.get("data") or []):
                    entity = a.get("entity", {})
                    alerts.append({
                        "type":     entity.get("type", ""),
                        "name":     entity.get("name", ""),
                        "code":     entity.get("code", ""),
                        "start":    datetime.fromtimestamp(
                            a.get("time", 0), tz=timezone.utc
                        ).strftime("%Y-%m-%d %H:%M UTC"),
                        "level":    a.get("level", ""),
                        "score":    a.get("overallScore", a.get("score", 0)),
                        "source":   a.get("datasource", ""),
                    })
    except Exception:
        pass
    return sorted(alerts, key=lambda x: x["score"], reverse=True)

async def _fetch_ioda_countries(session):
    """Fetch current signal level for top countries."""
    countries = []
    try:
        now   = int(time.time())
        since = now - 3600  # last hour
        async with session.get(
            f"{IODA_BASE}/signals/raw/country",
            params={"from": since, "until": now, "datasource": "bgp", "limit": 60},
            timeout=aiohttp.ClientTimeout(total=20)
        ) as r:
            if r.status == 200:
                d = await r.json()
                for entity in (d.get("data") or []):
                    meta   = entity.get("entity", {})
                    series = entity.get("values", [])
                    scores = [v for v in series if v is not None]
                    latest = scores[-1] if scores else None
                    countries.append({
                        "country": meta.get("name", ""),
                        "code":    meta.get("code", ""),
                        "score":   round(latest, 2) if latest is not None else None,
                        "normal":  round(sum(scores) / len(scores), 2) if scores else None,
                    })
    except Exception:
        pass
    return sorted(countries, key=lambda x: x["country"])

async def _fetch_bgp_hijacks(session):
    """RIPE NCC BGP hijack alerts."""
    events = []
    try:
        async with session.get(
            f"{RIPE_BASE}/bgp-updates/data.json",
            params={"resource": "0.0.0.0/0", "starttime": "2h", "endtime": "now"},
            timeout=aiohttp.ClientTimeout(total=15)
        ) as r:
            if r.status == 200:
                d = await r.json()
                updates = (d.get("data") or {}).get("updates", [])
                for u in updates[:30]:
                    events.append({
                        "prefix":  u.get("prefix", ""),
                        "type":    u.get("type", ""),
                        "peer":    u.get("peer", ""),
                        "origin":  u.get("origin_asn", ""),
                        "time":    u.get("timestamp", ""),
                    })
    except Exception:
        pass

    # Also try RIPE routing consistency
    try:
        async with session.get(
            "https://stat.ripe.net/data/routing-history/data.json"
            "?resource=8.8.8.8&max_rows=5",
            timeout=aiohttp.ClientTimeout(total=10)
        ) as r:
            pass  # just a connectivity check
    except Exception:
        pass

    return events

async def run_poller(interval: int = 300):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                alerts, countries, bgp = await asyncio.gather(
                    _fetch_ioda_alerts(session),
                    _fetch_ioda_countries(session),
                    _fetch_bgp_hijacks(session),
                    return_exceptions=True,
                )
                _state.alerts    = alerts    if isinstance(alerts, list)    else []
                _state.countries = countries if isinstance(countries, list) else []
                _state.bgp       = bgp       if isinstance(bgp, list)       else []
                _state.updated   = time.time()
                _state.error     = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
