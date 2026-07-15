"""WHO Global Health Observatory — free REST API, no key."""

import asyncio
import aiohttp
import time
from dataclasses import dataclass, field
from typing import Optional

GHO_BASE = "https://ghoapi.azureedge.net/api"

# (indicator_code, label, unit)
INDICATORS = [
    ("WHOSIS_000001",       "Life Expectancy",            "years"),
    ("MDG_0000000026",      "Under-5 Mortality",          "per 1,000"),
    ("MORT_100",            "Adult Mortality (M)",        "per 1,000"),
    ("MORT_200",            "Adult Mortality (F)",        "per 1,000"),
    ("HIV_0000000001",      "HIV Prevalence",             "%"),
    ("MALARIA_EST_DEATHS",  "Malaria Deaths",             "thousands"),
    ("TB_e_inc_100k",       "TB Incidence",               "per 100k"),
    ("NCD_BMI_30A",         "Obesity Rate",               "%"),
    ("SA_0000001462",       "Alcohol Consumption",        "L/yr"),
    ("NUTRITION_ANAEMIA_CHILDREN_PREV", "Child Anaemia", "%"),
]


@dataclass
class WhoState:
    by_country:  dict = field(default_factory=dict)   # country_code -> {indicator -> value}
    indicators:  list = field(default_factory=list)   # [{code, label, unit}]
    updated:     float = 0.0
    error:       Optional[str] = None


_state = WhoState()


def get_who():
    return _state


async def _fetch_indicator(session: aiohttp.ClientSession, code: str) -> dict:
    """Return {country_code: latest_numeric_value} for one indicator."""
    result = {}
    try:
        url = f"{GHO_BASE}/{code}?$filter=Dim1%20eq%20%27SEX_BTSX%27%20or%20Dim1%20eq%20null&$orderby=TimeDim%20desc&$top=300"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status != 200:
                return result
            data = (await r.json()).get("value", [])
        # Keep only most recent value per country
        seen = set()
        for row in data:
            country = row.get("SpatialDim", "")
            val     = row.get("NumericValue")
            if country and val is not None and country not in seen:
                result[country] = float(val)
                seen.add(country)
    except Exception:
        pass
    return result


async def run_poller(interval: int = 86400):  # daily
    global _state
    async with aiohttp.ClientSession(headers={"User-Agent": "OpenBloomberg/1.0"}) as session:
        while True:
            try:
                results = await asyncio.gather(
                    *[_fetch_indicator(session, code) for code, _, _ in INDICATORS],
                    return_exceptions=True,
                )
                by_country: dict = {}
                ind_meta = []
                for (code, label, unit), res in zip(INDICATORS, results):
                    ind_meta.append({"code": code, "label": label, "unit": unit})
                    if isinstance(res, dict):
                        for country, val in res.items():
                            if country not in by_country:
                                by_country[country] = {}
                            by_country[country][code] = val

                _state.by_country = by_country
                _state.indicators = ind_meta
                _state.updated    = time.time()
                _state.error      = None
            except Exception as e:
                _state.error = str(e)
            await asyncio.sleep(interval)
