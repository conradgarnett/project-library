"""
Cyber threat intelligence — CISA advisories (free, no key).

Sources:
  - CISA All Cybersecurity Advisories RSS
  - CISA ICS-CERT Advisories RSS
"""
import asyncio, aiohttp, time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from xml.etree import ElementTree as ET

FEEDS = [
    ("https://www.cisa.gov/cybersecurity-advisories/all.xml",          "CISA"),
    ("https://www.cisa.gov/cybersecurity-advisories/ics-advisories.xml","CISA ICS"),
]

SEVERITY_WORDS = {
    "critical":           "CRITICAL",
    "high":               "HIGH",
    "known exploited":    "HIGH",
    "actively exploited": "HIGH",
    "medium":             "MEDIUM",
    "low":                "LOW",
}


@dataclass
class ThreatState:
    advisories: list  = field(default_factory=list)
    updated:    float = 0.0
    error:      Optional[str] = None


_state = ThreatState()


def get_threats():
    return _state


def _severity(text: str) -> str:
    lower = text.lower()
    for word, label in SEVERITY_WORDS.items():
        if word in lower:
            return label
    return "INFO"


def _parse_rss(xml_text: str, source: str) -> list:
    items = []
    try:
        root = ET.fromstring(xml_text)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}

        # Atom feed
        for entry in root.findall("atom:entry", ns):
            title   = entry.findtext("atom:title",   "", ns).strip()
            summary = entry.findtext("atom:summary", "", ns).strip()
            updated = entry.findtext("atom:updated", "", ns).strip()
            link_el = entry.find("atom:link", ns)
            link    = (link_el.get("href", "") if link_el is not None else "")
            try:
                dt = datetime.fromisoformat(updated.replace("Z", "+00:00"))
                date_s = dt.strftime("%Y-%m-%d")
            except Exception:
                date_s = updated[:10] if updated else ""
            items.append({
                "title":    title,
                "summary":  (summary or title)[:200],
                "date":     date_s,
                "source":   source,
                "severity": _severity(title + " " + summary),
                "link":     link,
            })

        # RSS feed
        if not items:
            for item in root.findall(".//item"):
                title   = (item.findtext("title") or "").strip()
                desc    = (item.findtext("description") or "").strip()
                pub     = (item.findtext("pubDate") or "").strip()
                link    = (item.findtext("link") or "").strip()
                try:
                    dt = parsedate_to_datetime(pub)
                    date_s = dt.strftime("%Y-%m-%d")
                except Exception:
                    date_s = pub[:10] if pub else ""
                items.append({
                    "title":    title,
                    "summary":  (desc or title)[:200],
                    "date":     date_s,
                    "source":   source,
                    "severity": _severity(title + " " + desc),
                    "link":     link,
                })
    except Exception:
        pass
    return items


async def _fetch_feed(session: aiohttp.ClientSession, url: str, source: str) -> list:
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=12)) as r:
            if r.status != 200:
                return []
            text = await r.text()
            return _parse_rss(text, source)
    except Exception:
        return []


async def run_poller(interval: int = 1800):
    global _state
    while True:
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": "OpenBloombergTerminal/2.0"}
            ) as session:
                results = await asyncio.gather(
                    *[_fetch_feed(session, url, src) for url, src in FEEDS],
                    return_exceptions=True,
                )
            all_items = []
            for r in results:
                if isinstance(r, list):
                    all_items.extend(r)

            all_items.sort(key=lambda x: x.get("date", ""), reverse=True)

            _state.advisories = all_items[:60]
            _state.updated    = time.time()
            _state.error      = None
        except Exception as e:
            _state.error = str(e)
        await asyncio.sleep(interval)
