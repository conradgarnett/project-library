"""FRED macro data — St. Louis Fed (free key required, register at fred.stlouisfed.org)."""
import asyncio, aiohttp, os, time
from dataclasses import dataclass, field
from typing import Optional

API_KEY = os.environ.get("FRED_API_KEY", "")   # set env var or leave blank for demo data

# Key series for the dashboard presets
DASHBOARD_SERIES = {
    # US Economy
    "GDP Growth":       "A191RL1Q225SBEA",   # Real GDP growth QoQ annualized
    "CPI YoY":          "CPIAUCSL",
    "Core PCE YoY":     "PCEPILFE",
    "Unemployment":     "UNRATE",
    "Fed Funds Rate":   "FEDFUNDS",
    "10Y Treasury":     "DGS10",
    "2Y Treasury":      "DGS2",
    "10Y-2Y Spread":    "T10Y2Y",
    "M2 YoY":           "M2SL",
    "Consumer Sentiment": "UMCSENT",
    "Housing Starts":   "HOUST",
    "Retail Sales MoM": "RSXFS",
    # Inflation
    "5Y Breakeven":     "T5YIE",
    "10Y Breakeven":    "T10YIE",
    "Median CPI":       "MEDCPIM158SFRBCLE",
    # Global
    "US Debt/GDP":      "GFDEGDQ188S",
    "Trade Balance":    "BOPGSTB",
    "ISM Manufacturing":"MANEMP",
}

@dataclass
class FredState:
    series: dict   = field(default_factory=dict)   # series_id -> {title, value, date, unit, prev, change}
    updated: float = 0.0
    error: Optional[str] = None

_state = FredState()

def get_fred():
    return _state

async def _fetch_series(session, series_id: str) -> Optional[dict]:
    if not API_KEY:
        return None
    try:
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id={series_id}&api_key={API_KEY}&file_type=json"
            f"&sort_order=desc&limit=2"
        )
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status == 200:
                d = await r.json()
                obs = [o for o in d.get("observations", []) if o.get("value") != "."]
                if obs:
                    latest = obs[0]
                    prev   = obs[1] if len(obs) > 1 else None
                    val  = float(latest["value"])
                    pval = float(prev["value"]) if prev else val
                    return {
                        "series_id": series_id,
                        "value":  val,
                        "date":   latest["date"],
                        "prev":   pval,
                        "change": round(val - pval, 4),
                    }
    except Exception:
        pass
    return None

async def fetch_series_history(series_id: str, limit: int = 60) -> list:
    """Return list of {date, value} for charting."""
    if not API_KEY:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={series_id}&api_key={API_KEY}&file_type=json"
                f"&sort_order=desc&limit={limit}"
            )
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status == 200:
                    d = await r.json()
                    obs = [
                        {"date": o["date"], "value": float(o["value"])}
                        for o in reversed(d.get("observations", []))
                        if o.get("value") != "."
                    ]
                    return obs
    except Exception:
        pass
    return []

async def run_poller(interval: int = 3600):
    global _state
    while True:
        if API_KEY:
            try:
                async with aiohttp.ClientSession() as session:
                    tasks = [_fetch_series(session, sid) for sid in DASHBOARD_SERIES.values()]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    sid_list = list(DASHBOARD_SERIES.values())
                    name_map = {v: k for k, v in DASHBOARD_SERIES.items()}
                    for sid, result in zip(sid_list, results):
                        if isinstance(result, dict):
                            result["name"] = name_map.get(sid, sid)
                            _state.series[sid] = result
                _state.updated = time.time()
                _state.error = None
            except Exception as e:
                _state.error = str(e)
        else:
            _state.error = "Set FRED_API_KEY environment variable (free at fred.stlouisfed.org)"
        await asyncio.sleep(interval)
