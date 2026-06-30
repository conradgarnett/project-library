"""
News headlines from public RSS feeds — no API key required.
Sources: Reuters, BBC, AP, Financial Times, Bloomberg (free), etc.
"""

import asyncio
import time
import hashlib
import aiohttp
import feedparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

RSS_FEEDS = {
    "Reuters":         "https://feeds.reuters.com/reuters/topNews",
    "Reuters Markets": "https://feeds.reuters.com/reuters/businessNews",
    "BBC World":       "https://feeds.bbci.co.uk/news/world/rss.xml",
    "BBC Business":    "https://feeds.bbci.co.uk/news/business/rss.xml",
    "AP News":         "https://rsshub.app/apnews/topics/apf-topnews",
    "AP Business":     "https://rsshub.app/apnews/topics/apf-business",
    "FT":              "https://www.ft.com/rss/home",
    "WSJ":             "https://feeds.a.dj.com/rss/RSSWorldNews.xml",
    "WSJ Markets":     "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "CNBC":            "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "MarketWatch":     "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "Ars Technica":    "https://feeds.arstechnica.com/arstechnica/index",
    "Hacker News":     "https://hnrss.org/frontpage",
    "SpaceNews":       "https://spacenews.com/feed/",
    "FlightGlobal":    "https://www.flightglobal.com/rss/",
    "Lloyd's List":    "https://www.lloydslist.com/rss/",
}

CATEGORIES = {
    "Top":      ["Reuters", "BBC World", "AP News"],
    "Markets":  ["Reuters Markets", "WSJ Markets", "CNBC", "MarketWatch", "WSJ"],
    "Business": ["BBC Business", "FT", "AP Business"],
    "Tech":     ["Ars Technica", "Hacker News"],
    "Space":    ["SpaceNews"],
    "Aviation": ["FlightGlobal"],
    "Shipping": ["Lloyd's List"],
}


@dataclass
class Article:
    id: str
    source: str
    title: str
    summary: str
    link: str
    published: Optional[datetime]
    category: str = "Top"

    @property
    def time_ago(self) -> str:
        if not self.published:
            return "?"
        delta = datetime.now(timezone.utc) - self.published.replace(tzinfo=timezone.utc) if self.published.tzinfo is None else datetime.now(timezone.utc) - self.published
        secs = int(delta.total_seconds())
        if secs < 0:
            return "now"
        if secs < 60:
            return f"{secs}s"
        elif secs < 3600:
            return f"{secs // 60}m"
        elif secs < 86400:
            return f"{secs // 3600}h"
        return f"{secs // 86400}d"


@dataclass
class NewsState:
    articles: list[Article] = field(default_factory=list)
    by_category: dict[str, list[Article]] = field(default_factory=dict)
    updated: float = field(default_factory=time.time)
    sources_ok: int = 0
    sources_fail: int = 0


_state = NewsState()
_seen_ids: set[str] = set()


def get_news() -> NewsState:
    return _state


def _find_category(source: str) -> str:
    for cat, sources in CATEGORIES.items():
        if source in sources:
            return cat
    return "Business"


async def _fetch_feed(session: aiohttp.ClientSession, source: str, url: str) -> list[Article]:
    articles = []
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as r:
            if r.status not in (200, 301, 302):
                return []
            content = await r.read()
            feed = feedparser.parse(content)
            cat = _find_category(source)
            for entry in (feed.entries or [])[:10]:
                try:
                    title = entry.get("title", "").strip()
                    if not title:
                        continue
                    link    = entry.get("link", "")
                    summary = entry.get("summary", entry.get("description", ""))[:200]

                    # Parse date
                    published = None
                    for key in ("published_parsed", "updated_parsed"):
                        if hasattr(entry, key) and getattr(entry, key):
                            import calendar
                            t = getattr(entry, key)
                            published = datetime.utcfromtimestamp(calendar.timegm(t))
                            break

                    art_id = hashlib.md5(f"{source}:{title}".encode()).hexdigest()[:12]
                    articles.append(Article(
                        id=art_id, source=source, title=title,
                        summary=summary, link=link,
                        published=published, category=cat,
                    ))
                except Exception:
                    pass
    except Exception:
        pass
    return articles


async def run_poller(interval: int = 120):
    global _state, _seen_ids
    async with aiohttp.ClientSession(headers={
        "User-Agent": "Mozilla/5.0 (compatible; OpenBloomberg/1.0)"
    }) as session:
        while True:
            all_articles: list[Article] = []
            ok = fail = 0

            tasks = [_fetch_feed(session, src, url) for src, url in RSS_FEEDS.items()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, list) and result:
                    all_articles.extend(result)
                    ok += 1
                else:
                    fail += 1

            # Sort by published date (newest first)
            all_articles.sort(key=lambda a: a.published or datetime.min, reverse=True)

            by_cat: dict[str, list[Article]] = {}
            for a in all_articles:
                by_cat.setdefault(a.category, []).append(a)

            _state = NewsState(
                articles=all_articles[:200],
                by_category=by_cat,
                updated=time.time(),
                sources_ok=ok,
                sources_fail=fail,
            )
            await asyncio.sleep(interval)
