"""
Global Trade monitor
Sources:
  - World Bank Open Data (no key) — exports + imports by country
    https://api.worldbank.org/v2/
  - UN Comtrade public preview (no key) — single-country totals
    https://comtradeapi.un.org/public/v1/preview/C/A/HS
"""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

# World Bank country codes → display name
COUNTRIES = {
    "US": "United States", "CN": "China",         "DE": "Germany",
    "JP": "Japan",         "GB": "United Kingdom","FR": "France",
    "KR": "South Korea",   "CA": "Canada",        "IT": "Italy",
    "IN": "India",         "NL": "Netherlands",   "MX": "Mexico",
    "BR": "Brazil",        "SG": "Singapore",     "AU": "Australia",
    "CH": "Switzerland",   "SA": "Saudi Arabia",  "SE": "Sweden",
    "BE": "Belgium",       "TH": "Thailand",      "ES": "Spain",
    "RU": "Russia",        "AE": "UAE",           "ZA": "South Africa",
    "NG": "Nigeria",       "AR": "Argentina",     "MY": "Malaysia",
    "ID": "Indonesia",     "PL": "Poland",        "TW": "Taiwan",
}

# World Bank indicator codes
IND_EXP = "NE.EXP.GNFS.CD"   # exports of goods and services (current USD)
IND_IMP = "NE.IMP.GNFS.CD"   # imports of goods and services (current USD)

WB_BASE = "https://api.worldbank.org/v2"


@dataclass
class TradeState:
    countries: list         = field(default_factory=list)  # [{iso, country, exports_bn, imports_bn, balance_bn, year}]
    updated:   float        = 0.0
    error:     Optional[str] = None


_state = TradeState()


def get_trade():
    return _state


async def _wb_indicator(session: aiohttp.ClientSession, indicator: str, codes: list) -> dict:
    """Fetch latest value for multiple countries from World Bank."""
    code_str = ";".join(codes)
    url = (f"{WB_BASE}/country/{code_str}/indicator/{indicator}"
           f"?format=json&mrv=3&per_page=200")
    result = {}
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
            if r.status != 200:
                return result
            data = await r.json()
            # data is [meta, [records...]]
            records = data[1] if (isinstance(data, list) and len(data) > 1) else []
            for rec in (records or []):
                if rec.get("value") is None:
                    continue
                iso = rec.get("countryiso3code") or rec.get("country", {}).get("id", "")
                # Convert ISO3 → ISO2
                iso2 = _iso3_to_iso2(iso)
                if iso2 and iso2 not in result:
                    result[iso2] = {
                        "value": float(rec["value"]),
                        "year":  rec.get("date", ""),
                    }
    except Exception:
        pass
    return result


_ISO3 = {
    "USA": "US", "CHN": "CN", "DEU": "DE", "JPN": "JP", "GBR": "GB",
    "FRA": "FR", "KOR": "KR", "CAN": "CA", "ITA": "IT", "IND": "IN",
    "NLD": "NL", "MEX": "MX", "BRA": "BR", "SGP": "SG", "AUS": "AU",
    "CHE": "CH", "SAU": "SA", "SWE": "SE", "BEL": "BE", "THA": "TH",
    "ESP": "ES", "RUS": "RU", "ARE": "AE", "ZAF": "ZA", "NGA": "NG",
    "ARG": "AR", "MYS": "MY", "IDN": "ID", "POL": "PL", "TWN": "TW",
}


def _iso3_to_iso2(iso3: str) -> str:
    return _ISO3.get(iso3, iso3[:2] if len(iso3) == 3 else "")


async def run_poller(interval: int = 86400):
    global _state
    while True:
        try:
            codes = list(COUNTRIES.keys())
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                exp_data, imp_data = await asyncio.gather(
                    _wb_indicator(session, IND_EXP, codes),
                    _wb_indicator(session, IND_IMP, codes),
                )

            rows = []
            for iso, name in COUNTRIES.items():
                exp = exp_data.get(iso)
                imp = imp_data.get(iso)
                if not exp and not imp:
                    continue
                exp_bn  = round(exp["value"] / 1e9, 1)  if exp else None
                imp_bn  = round(imp["value"] / 1e9, 1)  if imp else None
                bal_bn  = round(exp_bn - imp_bn, 1)     if (exp_bn and imp_bn) else None
                year    = exp["year"] if exp else (imp["year"] if imp else "")
                rows.append({
                    "iso":        iso,
                    "country":    name,
                    "exports_bn": exp_bn,
                    "imports_bn": imp_bn,
                    "balance_bn": bal_bn,
                    "year":       year,
                })

            # Sort by exports descending
            rows.sort(key=lambda r: r["exports_bn"] or 0, reverse=True)
            _state.countries = rows
            _state.updated   = time.time()
            _state.error     = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
