"""Treasury yield curve + FRED bond data."""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class YieldCurveState:
    maturities: list = field(default_factory=list)   # [{"label":"3M","years":0.25,"yield":5.32}, ...]
    history: dict = field(default_factory=dict)       # date -> {maturity: yield}
    spread_10y2y: float = 0.0
    updated: float = 0.0
    error: Optional[str] = None

_state = YieldCurveState()

MATURITIES = [
    ("1 Mo", "BC_1MONTH"), ("2 Mo", "BC_2MONTH"), ("3 Mo", "BC_3MONTH"),
    ("6 Mo", "BC_6MONTH"), ("1 Yr", "BC_1YEAR"),  ("2 Yr", "BC_2YEAR"),
    ("3 Yr", "BC_3YEAR"),  ("5 Yr", "BC_5YEAR"),  ("7 Yr", "BC_7YEAR"),
    ("10 Yr","BC_10YEAR"), ("20 Yr","BC_20YEAR"),  ("30 Yr","BC_30YEAR"),
]

YEARS_MAP = {
    "BC_1MONTH":0.083,"BC_2MONTH":0.167,"BC_3MONTH":0.25,"BC_6MONTH":0.5,
    "BC_1YEAR":1,"BC_2YEAR":2,"BC_3YEAR":3,"BC_5YEAR":5,"BC_7YEAR":7,
    "BC_10YEAR":10,"BC_20YEAR":20,"BC_30YEAR":30,
}

def get_bonds():
    return _state

async def _fetch_treasury_xml(session) -> dict:
    """Try Treasury's current XML endpoint, return {col: yield} dict or {}."""
    import re
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    for i in range(3):
        dt = now - timedelta(days=i * 30)
        url = (
            "https://home.treasury.gov/resource-center/data-chart-center/"
            f"interest-rates/pages/xml?data=daily_treasury_yield_curve"
            f"&field_tdr_date_value_month={dt.strftime('%Y%m')}"
        )
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                if r.status != 200:
                    continue
                text = await r.text()
                yields = {}
                for label, col in MATURITIES:
                    # Handle `d:` namespace with optional XML attributes (e.g. m:type="Edm.Double")
                    m = re.findall(rf'<(?:d:)?{col}[^>]*>([\d.]+)</', text)
                    if not m:
                        # Also try plain tag without namespace
                        m = re.findall(rf'<{col}[^>]*>([\d.]+)</', text)
                    if m:
                        yields[col] = float(m[-1])
                if yields:
                    return yields
        except Exception:
            continue
    return {}


async def _fetch_treasury_yf() -> dict:
    """Fallback: get 10Y and 3M yields from yfinance, return partial {col: yield}."""
    import asyncio
    def _yf_get():
        import yfinance as yf
        result = {}
        try:
            tnx = yf.Ticker("^TNX").fast_info
            val = float(tnx.last_price or 0)
            if val > 0:
                result["BC_10YEAR"] = val
        except Exception:
            pass
        try:
            irx = yf.Ticker("^IRX").fast_info
            val = float(irx.last_price or 0)
            if val > 0:
                result["BC_3MONTH"] = val
        except Exception:
            pass
        try:
            fvx = yf.Ticker("^FVX").fast_info
            val = float(fvx.last_price or 0)
            if val > 0:
                result["BC_5YEAR"] = val
        except Exception:
            pass
        return result

    from feeds.yf_throttle import run as yf_run
    return await yf_run(_yf_get)


async def run_poller(interval: int = 3600):
    global _state
    while True:
        try:
            yields = {}
            async with aiohttp.ClientSession() as session:
                yields = await _fetch_treasury_xml(session)

            if not yields:
                # Treasury XML unavailable — use yfinance for key yields
                yields = await _fetch_treasury_yf()

            if yields:
                curve = []
                for label, col in MATURITIES:
                    if col in yields:
                        curve.append({
                            "label": label,
                            "years": YEARS_MAP[col],
                            "yield": yields[col],
                        })
                y10 = yields.get("BC_10YEAR", 0)
                y2  = yields.get("BC_2YEAR") or yields.get("BC_3MONTH", 0)
                _state.maturities = curve
                _state.spread_10y2y = round(y10 - y2, 3) if y10 and y2 else 0.0
                _state.updated = time.time()
                _state.error = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
