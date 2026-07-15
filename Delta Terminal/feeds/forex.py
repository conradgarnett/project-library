"""Forex rates via Frankfurter (ECB data, free, no key)."""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

PAIRS = [
    ("EUR/USD","EUR","USD"), ("GBP/USD","GBP","USD"), ("USD/JPY","USD","JPY"),
    ("USD/CHF","USD","CHF"), ("AUD/USD","AUD","USD"), ("USD/CAD","USD","CAD"),
    ("NZD/USD","NZD","USD"), ("EUR/GBP","EUR","GBP"), ("EUR/JPY","EUR","JPY"),
    ("GBP/JPY","GBP","JPY"), ("USD/CNY","USD","CNY"), ("USD/INR","USD","INR"),
    ("USD/MXN","USD","MXN"), ("USD/BRL","USD","BRL"), ("USD/KRW","USD","KRW"),
]

BASE_CURRENCIES = list({b for _,b,_ in PAIRS})

@dataclass
class ForexState:
    rates: dict  = field(default_factory=dict)   # "EUR/USD" -> {rate, prev, change_pct}
    updated: float = 0.0
    error: Optional[str] = None

_state = ForexState()

def get_forex():
    return _state

async def run_poller(interval: int = 60):
    global _state
    while True:
        try:
            results = {}
            async with aiohttp.ClientSession() as session:
                # Frankfurter returns all rates from a base in one call
                bases = set(b for _,b,_ in PAIRS)
                rate_map = {}
                for base in bases:
                    try:
                        async with session.get(
                            f"https://api.frankfurter.app/latest?from={base}",
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as r:
                            if r.status == 200:
                                d = await r.json()
                                for to_cur, val in d.get("rates", {}).items():
                                    rate_map[(base, to_cur)] = val
                                rate_map[(base, base)] = 1.0
                    except Exception:
                        continue

                # Fetch yesterday for change
                prev_map = {}
                try:
                    from datetime import datetime, timedelta
                    yday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
                    async with session.get(
                        f"https://api.frankfurter.app/{yday}?from=USD",
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as r:
                        if r.status == 200:
                            d = await r.json()
                            for to_cur, val in d.get("rates", {}).items():
                                prev_map[("USD", to_cur)] = val
                except Exception:
                    pass

            for name, base, quote in PAIRS:
                rate = rate_map.get((base, quote))
                if rate is None:
                    # Try inverse
                    inv = rate_map.get((quote, base))
                    if inv and inv != 0:
                        rate = 1 / inv
                if rate is None:
                    continue
                prev = None
                if base == "USD":
                    prev = prev_map.get(("USD", quote))
                elif quote == "USD":
                    p = prev_map.get(("USD", base))
                    if p and p != 0:
                        prev = 1 / p
                chg_pct = ((rate - prev) / prev * 100) if prev else 0.0
                results[name] = {"rate": rate, "prev": prev, "change_pct": round(chg_pct, 4)}

            if results:
                _state.rates = results
                _state.updated = time.time()
                _state.error = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
