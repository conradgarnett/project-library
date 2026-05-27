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

async def run_poller(interval: int = 3600):
    global _state
    from datetime import datetime, timedelta
    while True:
        try:
            # Treasury XML API
            now = datetime.utcnow()
            months = [now - timedelta(days=i*30) for i in range(3)]
            yields = {}
            async with aiohttp.ClientSession() as session:
                for dt in months:
                    url = (
                        "https://home.treasury.gov/resource-center/data-chart-center/"
                        f"interest-rates/TextView?type=daily_treasury_yield_curve"
                        f"&field_tdr_date_value={dt.strftime('%Y%m')}"
                    )
                    try:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
                            if r.status == 200:
                                text = await r.text()
                                # Parse XML table — find most recent row
                                import re
                                rows = re.findall(r'<t:NEW_DATE>(.*?)</t:NEW_DATE>.*?'
                                                  r'(<t:BC_[^<]*>.*?</t:BC_[^/]*>)+', text, re.DOTALL)
                                # Simpler: find all BC_ values in last occurrence
                                for label, col in MATURITIES:
                                    m = re.findall(rf'<t:{col}>([\d.]+)</t:{col}>', text)
                                    if m:
                                        yields[col] = float(m[-1])
                                if yields:
                                    break
                    except Exception:
                        continue

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
                y2  = yields.get("BC_2YEAR", 0)
                _state.maturities = curve
                _state.spread_10y2y = round(y10 - y2, 3)
                _state.updated = time.time()
                _state.error = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
