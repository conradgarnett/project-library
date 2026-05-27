"""World Bank Open Data — demographics & development indicators. Free, no key."""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class PopulationState:
    countries:  list = field(default_factory=list)  # [{country, code, pop, gdp_pc, life_exp, ...}]
    indicators: list = field(default_factory=list)  # [{series, name, value, year}]
    updated:    float = 0.0
    error:      Optional[str] = None

_state = PopulationState()

def get_population():
    return _state

WB_BASE = "https://api.worldbank.org/v2"

INDICATORS = {
    "SP.POP.TOTL":   "Population",
    "NY.GDP.PCAP.CD":"GDP per Capita (USD)",
    "SP.DYN.LE00.IN":"Life Expectancy",
    "SH.DYN.MORT":   "Child Mortality (per 1k)",
    "SE.ADT.LITR.ZS":"Adult Literacy Rate %",
    "SL.UEM.TOTL.ZS":"Unemployment %",
    "SP.URB.TOTL.IN.ZS":"Urban Population %",
    "EN.ATM.CO2E.PC":"CO₂ Emissions per Capita",
}

async def _fetch_indicator(session, code, name):
    url = (f"{WB_BASE}/country/all/indicator/{code}"
           f"?format=json&mrv=1&per_page=300")
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                d = await r.json()
                if isinstance(d, list) and len(d) > 1:
                    rows = [x for x in d[1] if x.get("value") is not None]
                    return code, rows
    except Exception:
        pass
    return code, []

async def run_poller(interval: int = 86400):  # daily — WB data rarely changes
    global _state
    while True:
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                results = {}
                for code, name in INDICATORS.items():
                    c, rows = await _fetch_indicator(session, code, name)
                    results[c] = {r["country"]["id"]: r for r in rows}
                    await asyncio.sleep(0.5)

                # build per-country table
                pop_code   = "SP.POP.TOTL"
                gdp_code   = "NY.GDP.PCAP.CD"
                life_code  = "SP.DYN.LE00.IN"
                unem_code  = "SL.UEM.TOTL.ZS"
                urb_code   = "SP.URB.TOTL.IN.ZS"

                country_ids = set(results.get(pop_code, {}).keys())
                countries = []
                for cid in country_ids:
                    pop_row = results.get(pop_code, {}).get(cid)
                    if not pop_row:
                        continue
                    cname = pop_row.get("country", {}).get("value", cid)
                    if cname in ("World", "Upper middle income", "Lower middle income",
                                 "High income", "Low income", "Middle income",
                                 "Low & middle income", "East Asia & Pacific",
                                 "Europe & Central Asia", "Latin America & Caribbean",
                                 "North America", "South Asia", "Sub-Saharan Africa",
                                 "Euro area", "OECD members"):
                        continue
                    def v(code): return (results.get(code,{}).get(cid,{}) or {}).get("value")
                    countries.append({
                        "code":      cid,
                        "country":   cname,
                        "pop":       v(pop_code),
                        "gdp_pc":    v(gdp_code),
                        "life_exp":  v(life_code),
                        "unemp":     v(unem_code),
                        "urban_pct": v(urb_code),
                    })

                # sort by population descending
                countries.sort(key=lambda x: x["pop"] or 0, reverse=True)
                _state.countries = countries[:200]

                # global indicators summary
                _state.indicators = [
                    {"code": code, "name": name,
                     "value": (results.get(code,{}).get("WLD",{}) or {}).get("value")}
                    for code, name in INDICATORS.items()
                ]
                _state.updated = time.time()
                _state.error   = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
