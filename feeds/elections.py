"""
Election calendar — 2026 national elections via Wikidata SPARQL (no key).
https://query.wikidata.org/sparql
"""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

SPARQL_URL = "https://query.wikidata.org/sparql"

def _make_query(year: int) -> str:
    return f"""
SELECT DISTINCT ?countryLabel ?date ?typeLabel ?article WHERE {{
  ?item wdt:P31/wdt:P279* wd:Q40231 .
  ?item wdt:P17 ?country .
  ?item wdt:P585 ?date .
  FILTER(YEAR(?date) = {year})
  ?item wdt:P31 ?type .
  OPTIONAL {{
    ?article schema:about ?item ;
             schema:isPartOf <https://en.wikipedia.org/> .
  }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}}
ORDER BY ?date
LIMIT 300
"""


@dataclass
class ElectionsState:
    elections: list          = field(default_factory=list)
    updated:   float         = 0.0
    error:     Optional[str] = None


_state = ElectionsState()


def get_elections():
    return _state


def _parse_date(s: str) -> str:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return s[:10] if s else ""


async def _sparql_fetch(session: aiohttp.ClientSession, query: str) -> list:
    headers = {
        "User-Agent": "OpenBloombergTerminal/2.0 (mailto:info@openbloomberg.io)",
        "Accept":     "application/sparql-results+json",
    }
    for attempt in range(3):
        try:
            async with session.get(
                SPARQL_URL, params={"query": query, "format": "json"},
                headers=headers, timeout=aiohttp.ClientTimeout(total=45)
            ) as r:
                if r.status == 429 or r.status >= 500:
                    await asyncio.sleep(10 * (attempt + 1))
                    continue
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                data = await r.json()
                return data.get("results", {}).get("bindings", [])
        except asyncio.TimeoutError:
            if attempt < 2:
                await asyncio.sleep(5)
    return []


async def run_poller(interval: int = 21600):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                b2025 = await _sparql_fetch(session, _make_query(2025))
                await asyncio.sleep(2)  # brief pause between Wikidata requests
                b2026 = await _sparql_fetch(session, _make_query(2026))

            rows = []
            seen = set()
            for binding in b2025 + b2026:
                country  = binding.get("countryLabel", {}).get("value", "")
                date_raw = binding.get("date",         {}).get("value", "")
                etype    = binding.get("typeLabel",    {}).get("value", "")
                article  = binding.get("article",      {}).get("value", "")
                date_s   = _parse_date(date_raw)

                # Deduplicate — keep first occurrence per country+date
                key = (country, date_s)
                if key in seen:
                    continue
                seen.add(key)

                # Skip non-national elections (regional, local, etc.)
                skip_words = ("regional", "municipal", "local", "state", "provincial",
                              "by-election", "byelection", "cantonal", "primary")
                if any(w in etype.lower() for w in skip_words):
                    continue

                rows.append({
                    "country": country,
                    "date":    date_s,
                    "type":    etype,
                    "wiki":    article,
                    "year":    date_s[:4] if date_s else "",
                })

            rows.sort(key=lambda r: r["date"])
            _state.elections = rows
            _state.updated   = time.time()
            _state.error     = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
