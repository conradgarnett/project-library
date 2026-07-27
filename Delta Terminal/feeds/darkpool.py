"""Dark pool & block trade data.

Block prints — derived from large-premium options flow (institutional proxies).
Short sale volume — FINRA RegSho daily data via api.finra.org (free, no key).
"""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

@dataclass
class DarkPoolState:
    prints:   list = field(default_factory=list)
    ats_vol:  list = field(default_factory=list)
    updated:  float = 0.0
    error:    Optional[str] = None

_state = DarkPoolState()

def get_darkpool():
    return _state

FINRA_REGSHO = "https://api.finra.org/data/group/otcmarket/name/regshoDaily"

async def _fetch_regsho_day(session: aiohttp.ClientSession, day: str) -> list:
    """Fetch one trading day's RegSho records via a date filter.
    A plain GET with only ?limit returns the OLDEST partition (months stale);
    FINRA requires an EQUAL compareFilter on tradeReportDate for current data."""
    body = {
        "limit": 5000,
        "compareFilters": [{
            "compareType": "EQUAL",
            "fieldName":   "tradeReportDate",
            "fieldValue":  day,
        }],
    }
    async with session.post(
        FINRA_REGSHO, json=body,
        headers={"Accept": "application/json"},
        timeout=aiohttp.ClientTimeout(total=20),
    ) as r:
        if r.status != 200:
            return []
        data = await r.json(content_type=None)
        return data if isinstance(data, list) else []


async def _fetch_regsho(session: aiohttp.ClientSession) -> list:
    """FINRA RegSho daily short sale volume — free, no key required."""
    try:
        rows = []
        # Walk back from today to find the most recent trading day with data
        data = []
        for back in range(7):
            day = (date.today() - timedelta(days=back)).isoformat()
            data = await _fetch_regsho_day(session, day)
            if data:
                break

        # Aggregate by symbol (multiple reporting facilities per symbol)
        by_sym: dict = {}
        for rec in (data if isinstance(data, list) else []):
            sym = rec.get("securitiesInformationProcessorSymbolIdentifier", "")
            if not sym or len(sym) > 5:
                continue
            if sym not in by_sym:
                by_sym[sym] = {"symbol": sym, "total": 0, "short": 0, "exempt": 0,
                               "date": rec.get("tradeReportDate", "")}
            by_sym[sym]["total"] += int(rec.get("totalParQuantity", 0) or 0)
            by_sym[sym]["short"] += int(rec.get("shortParQuantity", 0) or 0)
            by_sym[sym]["exempt"] += int(rec.get("shortExemptParQuantity", 0) or 0)

        for s in by_sym.values():
            if s["total"] > 0:
                s["short_pct"] = round(s["short"] / s["total"] * 100, 1)
            else:
                s["short_pct"] = 0.0
            rows.append(s)

        rows.sort(key=lambda x: x["total"], reverse=True)
        return rows[:150]
    except Exception:
        return []


def _derive_prints() -> list:
    """Derive large block prints from options flow unusual activity.
    Reads the options_flow feed state directly — no reason to loop back
    through our own HTTP server on a hardcoded port."""
    try:
        from feeds import options_flow
        unusual = options_flow.get_options_flow().unusual
        # Large premium options = institutional block activity
        blocks = [
            {
                "date":     u.get("expiry", ""),
                "ticker":   u.get("ticker", ""),
                "type":     "CALL" if u.get("type") == "C" else "PUT",
                "strike":   u.get("strike"),
                "expiry":   u.get("expiry"),
                "volume":   u.get("volume"),
                "premium_k": u.get("premium_k"),
                "value":    u.get("premium_k", 0) * 1000,
                "iv_pct":   u.get("iv_pct"),
                "itm":      u.get("itm"),
                "venue":    "OPTIONS",
            }
            for u in unusual
            if u.get("premium_k", 0) >= 50  # $50K+ premium = institutional
        ]
        blocks.sort(key=lambda x: x["premium_k"], reverse=True)
        return blocks[:80]
    except Exception:
        return []


async def run_poller(interval: int = 3600):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                ats_vol = await _fetch_regsho(session)
                _state.prints  = _derive_prints()
                _state.ats_vol = ats_vol
                _state.updated = time.time()
                _state.error   = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
