"""Geopolitical conflict & crisis news via free RSS feeds.
Sources: BBC World/Europe/Middle East, Al Jazeera, GDELT (fallback).
No API key required.
"""
import asyncio, aiohttp, time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class ConflictState:
    events:   list = field(default_factory=list)
    updated:  float = 0.0
    error:    Optional[str] = None

_state = ConflictState()

def get_conflicts():
    return _state

RSS_FEEDS = [
    # BBC regional feeds — reliable, well-structured, no rate limit
    ("https://feeds.bbci.co.uk/news/world/rss.xml",          "BBC World",  "world"),
    ("https://feeds.bbci.co.uk/news/world/middle_east/rss.xml","BBC ME",    "middle_east"),
    ("https://feeds.bbci.co.uk/news/world/europe/rss.xml",    "BBC Europe", "europe"),
    ("https://feeds.bbci.co.uk/news/world/africa/rss.xml",    "BBC Africa", "africa"),
    ("https://www.aljazeera.com/xml/rss/all.xml",             "Al Jazeera", "world"),
]

CONFLICT_KEYWORDS = {
    "war", "attack", "strike", "missile", "bomb", "troops", "military",
    "conflict", "fighting", "battle", "killed", "airstrike", "invasion",
    "ceasefire", "casualty", "casualties", "hostage", "siege", "assault",
    "protest", "riot", "coup", "sanctions", "crisis", "refugee",
    "humanitarian", "nuclear", "explosion", "drone", "offensive",
}

async def _fetch_rss(session: aiohttp.ClientSession, url: str, source: str, theme: str) -> list:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status != 200:
                return []
            xml_bytes = await r.read()
        root = ET.fromstring(xml_bytes)
        events = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link  = (item.findtext("link")  or "").strip()
            date  = (item.findtext("pubDate") or "")[:16]
            desc  = (item.findtext("description") or "")[:200]
            if not title:
                continue
            combined = (title + " " + desc).lower()
            if not any(kw in combined for kw in CONFLICT_KEYWORDS):
                continue
            events.append({
                "title":   title[:120],
                "url":     link,
                "domain":  source,
                "date":    date,
                "country": "",
                "theme":   theme,
                "image":   "",
            })
        return events
    except Exception:
        return []

async def run_poller(interval: int = 900):
    global _state
    while True:
        try:
            all_events = []
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloomberg/1.0"}
            ) as session:
                tasks = [_fetch_rss(session, url, src, theme) for url, src, theme in RSS_FEEDS]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, list):
                        all_events.extend(r)

            seen = set()
            deduped = []
            for e in all_events:
                key = e["url"] or e["title"]
                if key not in seen:
                    seen.add(key)
                    deduped.append(e)

            _state.events  = sorted(deduped, key=lambda x: x["date"], reverse=True)[:80]
            _state.updated = time.time()
            _state.error   = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
