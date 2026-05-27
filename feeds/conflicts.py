"""GDELT Project — geopolitical conflict & crisis news. Free, no key."""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ConflictState:
    events:   list = field(default_factory=list)   # [{title, url, domain, date, country, theme}]
    themes:   list = field(default_factory=list)   # top GDELT themes
    updated:  float = 0.0
    error:    Optional[str] = None

_state = ConflictState()

def get_conflicts():
    return _state

QUERIES = [
    ("war",       "war attack military offensive"),
    ("crisis",    "crisis emergency humanitarian"),
    ("protest",   "protest riot civil unrest"),
    ("coup",      "coup government overthrown"),
    ("sanctions", "sanctions embargo trade restriction"),
]

async def _fetch_gdelt(session, query, label):
    url = (
        "https://api.gdeltproject.org/api/v2/doc/doc"
        f"?query={query.replace(' ','%20')}&mode=artlist"
        "&maxrecords=15&format=json&timespan=24H"
        "&sourcelang=english"
    )
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                d = await r.json(content_type=None)
                arts = d.get("articles") or []
                return [
                    {
                        "title":   a.get("title","")[:120],
                        "url":     a.get("url",""),
                        "domain":  a.get("domain",""),
                        "date":    a.get("seendate","")[:8],
                        "country": a.get("sourcecountry",""),
                        "theme":   label,
                        "image":   a.get("socialimage",""),
                    }
                    for a in arts if a.get("title")
                ]
    except Exception:
        pass
    return []

async def run_poller(interval: int = 900):
    global _state
    while True:
        try:
            all_events = []
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                for label, query in QUERIES:
                    arts = await _fetch_gdelt(session, query, label)
                    all_events.extend(arts)
                    await asyncio.sleep(1)  # gentle on GDELT

            # deduplicate by url
            seen = set()
            deduped = []
            for e in all_events:
                if e["url"] not in seen:
                    seen.add(e["url"])
                    deduped.append(e)

            _state.events  = sorted(deduped, key=lambda x: x["date"], reverse=True)[:60]
            _state.updated = time.time()
            _state.error   = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
