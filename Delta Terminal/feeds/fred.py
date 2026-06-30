"""Macro series — multi-source: BLS, World Bank, yfinance futures, FRED.

Primary sources (no API key, always attempted first):
  - BLS Public API v1: unemployment rate, CPI YoY
  - World Bank Open Data: US real GDP growth
  - yfinance ZQ=F: implied Fed Funds rate from futures market

FRED (FRED_API_KEY required for most series):
  - 10-second timeout, fetches all remaining series in parallel
"""
import asyncio, aiohttp, os, time
from dataclasses import dataclass, field
from typing import Optional

FRED_KEY     = os.environ.get("FRED_API_KEY", "")
FRED_TIMEOUT = 10

DASHBOARD_SERIES = {
    "GDP Growth":         "A191RL1Q225SBEA",
    "CPI YoY":            "CPIAUCSL",
    "Unemployment":       "UNRATE",
    "Fed Funds Rate":     "FEDFUNDS",
    "10Y-2Y Spread":      "T10Y2Y",
    "Consumer Sentiment": "UMCSENT",
    "Core PCE YoY":       "PCEPILFE",
    "Housing Starts":     "HOUST",
    "Retail Sales MoM":   "RSXFS",
    "5Y Breakeven":       "T5YIE",
    "10Y Breakeven":      "T10YIE",
    "US Debt/GDP":        "GFDEGDQ188S",
    "Trade Balance":      "BOPGSTB",
    "10Y Treasury":       "DGS10",
    "2Y Treasury":        "DGS2",
    "M2 YoY":             "M2SL",
    "Mfg Employment":     "MANEMP",
    "Industrial Prod":    "IPMAN",
    "Mfg New Orders":     "AMTMNO",
    "Durable Goods":      "DGORDER",
}

SID_TO_NAME = {v: k for k, v in DASHBOARD_SERIES.items()}


@dataclass
class FredState:
    series:  dict  = field(default_factory=dict)
    updated: float = 0.0
    error:   Optional[str] = None


_state = FredState()


def get_fred():
    return _state


def _make(series_id: str, value: float, date: str, prev: Optional[float] = None) -> dict:
    p = prev if prev is not None else value
    return {
        "series_id": series_id,
        "name":   SID_TO_NAME.get(series_id, series_id),
        "value":  round(value, 4),
        "date":   date,
        "prev":   round(p, 4),
        "change": round(value - p, 4),
    }


# ── BLS Public API (no key) ───────────────────────────────────────────────────

async def _bls_latest(session: aiohttp.ClientSession, series_id: str) -> Optional[tuple]:
    """Return (value, date_str, prev_value) for a BLS series."""
    try:
        url = f"https://api.bls.gov/publicAPI/v1/timeseries/data/{series_id}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return None
            d = await r.json()
            if d.get("status") != "REQUEST_SUCCEEDED":
                return None
            data = d.get("Results", {}).get("series", [{}])[0].get("data", [])
            if not data:
                return None
            latest = data[0]
            prev   = data[1] if len(data) > 1 else None
            val    = float(latest["value"])
            pval   = float(prev["value"]) if prev else val
            mo     = latest["period"][1:]
            date_s = f"{latest['year']}-{mo}-01"
            return (val, date_s, pval)
    except Exception:
        return None


async def _bls_yoy(session: aiohttp.ClientSession, series_id: str) -> Optional[tuple]:
    """Return (yoy_pct, date_str, prev_yoy_pct) — year-over-year change for index series."""
    try:
        url = f"https://api.bls.gov/publicAPI/v1/timeseries/data/{series_id}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return None
            d = await r.json()
            if d.get("status") != "REQUEST_SUCCEEDED":
                return None
            data = d.get("Results", {}).get("series", [{}])[0].get("data", [])
            if len(data) < 13:
                return None
            cur   = float(data[0]["value"])
            yago  = float(data[12]["value"])
            yoy   = round((cur - yago) / yago * 100, 2) if yago else 0.0
            prev_cur  = float(data[1]["value"]) if len(data) > 1  else cur
            prev_yago = float(data[13]["value"]) if len(data) > 13 else yago
            prev_yoy  = round((prev_cur - prev_yago) / prev_yago * 100, 2) if prev_yago else yoy
            mo     = data[0]["period"][1:]
            date_s = f"{data[0]['year']}-{mo}-01"
            return (yoy, date_s, prev_yoy)
    except Exception:
        return None


# ── World Bank (no key) ───────────────────────────────────────────────────────

async def _wb_gdp(session: aiohttp.ClientSession) -> Optional[tuple]:
    """US real GDP growth rate from World Bank (annual, most recent available)."""
    try:
        url = (
            "https://api.worldbank.org/v2/country/US/indicator/"
            "NY.GDP.MKTP.KD.ZG?format=json&mrv=5&per_page=5"
        )
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status != 200:
                return None
            d = await r.json()
            entries = [e for e in (d[1] if len(d) > 1 else []) if e.get("value") is not None]
            if not entries:
                return None
            latest = entries[0]
            prev   = entries[1] if len(entries) > 1 else None
            val    = float(latest["value"])
            pval   = float(prev["value"]) if prev else val
            return (val, str(latest["date"]), pval)
    except Exception:
        return None


# ── yfinance Fed Funds futures ────────────────────────────────────────────────

async def _ff_from_futures() -> Optional[tuple]:
    """Implied Fed Funds rate from ZQ=F (30-day futures). Price = 100 - rate."""
    def _get():
        import yfinance as yf
        try:
            info  = yf.Ticker("ZQ=F").fast_info
            price = float(info.last_price or 0)
            prev  = float(info.previous_close or price)
            if price <= 0:
                return None
            rate      = round(100 - price, 3)
            prev_rate = round(100 - prev,  3)
            return (rate, time.strftime("%Y-%m-%d"), prev_rate)
        except Exception:
            return None

    from feeds.yf_throttle import run as yf_run
    return await yf_run(_get)


# ── FRED API ─────────────────────────────────────────────────────────────────

async def _fred_series(
    session: aiohttp.ClientSession,
    series_id: str,
    units: Optional[str] = None,
    limit: int = 2,
) -> Optional[dict]:
    """Fetch latest observations for a FRED series.
    units: None=level, 'pch'=% change from prior period, 'pc1'=% change from year ago.
    """
    if not FRED_KEY:
        return None
    try:
        params = {
            "series_id":  series_id,
            "api_key":    FRED_KEY,
            "file_type":  "json",
            "sort_order": "desc",
            "limit":      limit,
        }
        if units:
            params["units"] = units
        url = "https://api.stlouisfed.org/fred/series/observations"
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=FRED_TIMEOUT)) as r:
            if r.status != 200:
                return None
            d   = await r.json()
            obs = [o for o in d.get("observations", []) if o.get("value") not in (".", None)]
            if not obs:
                return None
            val  = float(obs[0]["value"])
            pval = float(obs[1]["value"]) if len(obs) > 1 else val
            return _make(series_id, val, obs[0]["date"], pval)
    except Exception:
        return None


async def fetch_series_history(series_id: str, limit: int = 60) -> list:
    """Chart history — FRED only (falls back to empty list if unavailable)."""
    if not FRED_KEY:
        return []
    try:
        async with aiohttp.ClientSession() as session:
            url = (
                f"https://api.stlouisfed.org/fred/series/observations"
                f"?series_id={series_id}&api_key={FRED_KEY}&file_type=json"
                f"&sort_order=desc&limit={limit}"
            )
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    d = await r.json()
                    return [
                        {"date": o["date"], "value": float(o["value"])}
                        for o in reversed(d.get("observations", []))
                        if o.get("value") not in (".", None)
                    ]
    except Exception:
        pass
    return []


# ── Main poller ───────────────────────────────────────────────────────────────

# FRED series to fetch: (series_id, units_or_None)
_FRED_CALLS = [
    ("T10Y2Y",      None),
    ("UMCSENT",     None),
    ("PCEPILFE",    "pc1"),
    ("HOUST",       None),
    ("RSXFS",       "pch"),
    ("T5YIE",       None),
    ("T10YIE",      None),
    ("GFDEGDQ188S", None),
    ("BOPGSTB",     None),
    ("DGS10",       None),
    ("DGS2",        None),
    ("M2SL",        "pc1"),
    ("MANEMP",      None),
    ("IPMAN",       None),
    ("AMTMNO",      None),
    ("DGORDER",     None),
]


async def run_poller(interval: int = 3600):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                # Free sources run in parallel (different providers, no shared rate limit)
                unrate_r, cpi_r, gdp_r, ff_r = await asyncio.gather(
                    _bls_latest(session, "LNS14000000"),   # Unemployment
                    _bls_yoy(session,   "CUUR0000SA0"),    # CPI YoY
                    _wb_gdp(session),                      # GDP growth
                    _ff_from_futures(),                    # Fed Funds implied
                    return_exceptions=True,
                )

                # FRED calls staggered to respect 120 req/min rate limit
                fred_results = {}
                for sid, units in _FRED_CALLS:
                    r = await _fred_series(session, sid, units=units)
                    fred_results[sid] = r
                    await asyncio.sleep(0.55)

            series: dict = {}

            def _store(sid, result):
                if isinstance(result, tuple):
                    val, date, prev = result
                    obj = _make(sid, val, date, prev)
                elif isinstance(result, dict):
                    obj = {**result, "name": SID_TO_NAME.get(result.get("series_id", sid), sid)}
                else:
                    return
                series[obj["name"]] = obj

            _store("UNRATE",          unrate_r)
            _store("CPIAUCSL",        cpi_r)
            _store("A191RL1Q225SBEA", gdp_r)
            _store("FEDFUNDS",        ff_r)
            for sid, _ in _FRED_CALLS:
                _store(sid, fred_results.get(sid))

            _state.series  = series
            _state.updated = time.time()
            _state.error   = None if series else "All macro sources failed"

        except Exception as e:
            _state.error = str(e)

        await asyncio.sleep(interval)
