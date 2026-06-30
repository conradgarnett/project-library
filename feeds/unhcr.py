"""UNHCR Global Trends — forced displacement data, free REST API, no key."""

import asyncio
import aiohttp
import time
from dataclasses import dataclass, field
from typing import Optional

UNHCR_BASE = "https://api.unhcr.org/population/v1"


@dataclass
class UnhcrState:
    totals:      dict  = field(default_factory=dict)   # global totals
    by_origin:   list  = field(default_factory=list)   # top countries of origin
    by_host:     list  = field(default_factory=list)   # top host countries
    updated:     float = 0.0
    error:       Optional[str] = None


_state = UnhcrState()


def get_unhcr():
    return _state


async def _get(session: aiohttp.ClientSession, path: str, params: dict) -> Optional[dict]:
    try:
        async with session.get(
            UNHCR_BASE + path, params=params,
            timeout=aiohttp.ClientTimeout(total=12),
        ) as r:
            if r.status == 200:
                return await r.json()
    except Exception:
        pass
    return None


async def run_poller(interval: int = 86400):  # daily
    global _state
    async with aiohttp.ClientSession(headers={"User-Agent": "OpenBloomberg/1.0"}) as session:
        while True:
            try:
                from datetime import datetime
                year = datetime.utcnow().year - 1  # most recent complete year

                # Global totals
                totals_r = await _get(session, "/population/", {
                    "limit": 1, "yearFrom": year, "yearTo": year,
                    "coo_all": "true", "coa_all": "true",
                })

                # By country of origin — top 50
                origin_r = await _get(session, "/population/", {
                    "limit": 50, "yearFrom": year, "yearTo": year,
                    "coa_all": "true",
                    "sortBy": "refugees", "sortDir": "desc",
                })

                # By host country — top 50
                host_r = await _get(session, "/population/", {
                    "limit": 50, "yearFrom": year, "yearTo": year,
                    "coo_all": "true",
                    "sortBy": "refugees", "sortDir": "desc",
                })

                def _agg(items):
                    total = {}
                    for row in (items or []):
                        for k in ("refugees", "asylum_seekers", "idps", "stateless", "ooc", "oip"):
                            v = row.get(k) or 0
                            try:
                                v = int(v)
                            except (TypeError, ValueError):
                                v = 0
                            total[k] = total.get(k, 0) + v
                    return total

                global_items = (totals_r or {}).get("items", [])
                totals = _agg(global_items)

                def _clean(rows):
                    out = []
                    for r in (rows or []):
                        out.append({
                            "country":    r.get("coo_name") or r.get("coa_name") or "?",
                            "iso":        r.get("coo_iso") or r.get("coa_iso") or "",
                            "refugees":   r.get("refugees") or 0,
                            "asylum":     r.get("asylum_seekers") or 0,
                            "idps":       r.get("idps") or 0,
                            "stateless":  r.get("stateless") or 0,
                            "year":       r.get("year") or year,
                        })
                    return out

                _state.totals    = totals
                _state.by_origin = _clean((origin_r or {}).get("items", []))
                _state.by_host   = _clean((host_r or {}).get("items", []))
                _state.updated   = time.time()
                _state.error     = None
            except Exception as e:
                _state.error = str(e)
            await asyncio.sleep(interval)
